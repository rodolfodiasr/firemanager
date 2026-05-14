"""F32.cont — Stripe Webhook: processa eventos invoice.paid, payment_failed, subscription atualizado."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter()


async def _verify_stripe_signature(payload: bytes, sig_header: str, secret: str) -> bool:
    """Verifica a assinatura do webhook Stripe via HMAC-SHA256."""
    import hashlib
    import hmac

    try:
        parts = dict(item.split("=", 1) for item in sig_header.split(","))
        timestamp = parts.get("t", "")
        signatures = [v for k, v in parts.items() if k == "v1"]
        signed_payload = f"{timestamp}.".encode() + payload
        expected = hmac.new(secret.encode(), signed_payload, hashlib.sha256).hexdigest()
        return any(hmac.compare_digest(expected, sig) for sig in signatures)
    except Exception:
        return False


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    stripe_signature: str = Header(None, alias="stripe-signature"),
) -> dict:
    from app.config import settings
    from app.models.product import BillingSubscription, BillingInvoice

    payload = await request.body()
    webhook_secret = getattr(settings, "stripe_webhook_secret", "")

    if webhook_secret and stripe_signature:
        if not await _verify_stripe_signature(payload, stripe_signature, webhook_secret):
            raise HTTPException(status_code=400, detail="Assinatura Stripe inválida.")

    try:
        event = json.loads(payload)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Payload inválido.")

    event_type = event.get("type", "")
    event_id = event.get("id", "")

    # Idempotency: skip duplicates
    from app.models.stripe_webhook_event import StripeWebhookEvent
    existing = await db.execute(
        select(StripeWebhookEvent).where(StripeWebhookEvent.stripe_event_id == event_id)
    )
    if existing.scalar_one_or_none():
        return {"status": "already_processed"}

    record = StripeWebhookEvent(
        stripe_event_id=event_id,
        event_type=event_type,
        payload=event,
    )
    db.add(record)
    await db.flush()

    data_obj = event.get("data", {}).get("object", {})

    try:
        if event_type == "invoice.paid":
            await _handle_invoice_paid(db, data_obj)
        elif event_type == "invoice.payment_failed":
            await _handle_payment_failed(db, data_obj)
        elif event_type in ("customer.subscription.updated", "customer.subscription.deleted"):
            await _handle_subscription_change(db, data_obj, event_type)

        record.processed = True
        record.processed_at = datetime.now(timezone.utc)
    except Exception as e:
        record.error = str(e)

    await db.commit()
    return {"status": "ok"}


async def _handle_invoice_paid(db, invoice_obj: dict) -> None:
    from app.models.product import BillingInvoice, BillingSubscription
    stripe_sub_id = invoice_obj.get("subscription", "")
    stripe_inv_id = invoice_obj.get("id", "")

    sub_result = await db.execute(
        select(BillingSubscription).where(BillingSubscription.stripe_subscription_id == stripe_sub_id)
    )
    sub = sub_result.scalar_one_or_none()
    if sub:
        sub.status = "active"

    inv_result = await db.execute(
        select(BillingInvoice).where(BillingInvoice.stripe_invoice_id == stripe_inv_id)
    )
    inv = inv_result.scalar_one_or_none()
    if inv:
        inv.status = "paid"
        inv.paid_at = datetime.now(timezone.utc)


async def _handle_payment_failed(db, invoice_obj: dict) -> None:
    from app.models.product import BillingSubscription
    stripe_sub_id = invoice_obj.get("subscription", "")
    sub_result = await db.execute(
        select(BillingSubscription).where(BillingSubscription.stripe_subscription_id == stripe_sub_id)
    )
    sub = sub_result.scalar_one_or_none()
    if sub:
        sub.status = "past_due"


async def _handle_subscription_change(db, sub_obj: dict, event_type: str) -> None:
    from app.models.product import BillingSubscription
    stripe_sub_id = sub_obj.get("id", "")
    result = await db.execute(
        select(BillingSubscription).where(BillingSubscription.stripe_subscription_id == stripe_sub_id)
    )
    sub = result.scalar_one_or_none()
    if not sub:
        return
    if event_type == "customer.subscription.deleted":
        sub.status = "canceled"
    else:
        stripe_status = sub_obj.get("status", "active")
        status_map = {
            "active": "active", "trialing": "trialing",
            "past_due": "past_due", "canceled": "canceled",
            "unpaid": "past_due",
        }
        sub.status = status_map.get(stripe_status, "active")
