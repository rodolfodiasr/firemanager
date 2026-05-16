"""F32.cont — Stripe Webhook: processa eventos checkout.session.completed,
invoice.paid, invoice.payment_failed, customer.subscription.deleted."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Header, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter()


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

    # Use stripe SDK for signature verification when secret is configured
    if webhook_secret and stripe_signature:
        try:
            import stripe as stripe_lib
            stripe_lib.api_key = getattr(settings, "stripe_secret_key", "")
            event_obj = stripe_lib.Webhook.construct_event(
                payload, stripe_signature, webhook_secret
            )
            event = event_obj
        except Exception:
            raise HTTPException(status_code=400, detail="Assinatura Stripe inválida.")
    else:
        try:
            event = json.loads(payload)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail="Payload inválido.")

    # Normalise: stripe SDK returns a StripeObject, raw JSON returns a dict
    if hasattr(event, "to_dict"):
        event = event.to_dict()

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
        if event_type == "checkout.session.completed":
            await _handle_checkout_completed(db, data_obj)
        elif event_type == "invoice.paid":
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


async def _handle_checkout_completed(db, session_obj: dict) -> None:
    """checkout.session.completed → criar/atualizar BillingSubscription."""
    from app.models.product import BillingSubscription, BillingPlan
    import uuid

    stripe_customer_id = session_obj.get("customer", "")
    stripe_subscription_id = session_obj.get("subscription", "")
    metadata = session_obj.get("metadata", {})

    tenant_id_str = metadata.get("tenant_id", "")
    plan_id_str = metadata.get("plan_id", "")

    if not tenant_id_str:
        return

    try:
        tenant_id = uuid.UUID(tenant_id_str)
    except ValueError:
        return

    # Find or create subscription
    sub_result = await db.execute(
        select(BillingSubscription).where(BillingSubscription.tenant_id == tenant_id)
    )
    sub = sub_result.scalar_one_or_none()

    if sub:
        sub.stripe_customer_id = stripe_customer_id
        sub.stripe_subscription_id = stripe_subscription_id
        sub.status = "active"
        # Update plan if provided
        if plan_id_str:
            try:
                plan_id = uuid.UUID(plan_id_str)
                sub.plan_id = plan_id
            except ValueError:
                pass
    else:
        # Determine plan
        plan_id = None
        if plan_id_str:
            try:
                plan_id = uuid.UUID(plan_id_str)
            except ValueError:
                pass

        if plan_id is None:
            # Fallback to starter
            starter = await db.scalar(select(BillingPlan).where(BillingPlan.slug == "starter"))
            plan_id = starter.id if starter else None

        if plan_id:
            sub = BillingSubscription(
                tenant_id=tenant_id,
                plan_id=plan_id,
                stripe_customer_id=stripe_customer_id,
                stripe_subscription_id=stripe_subscription_id,
                status="active",
            )
            db.add(sub)

    await db.flush()


async def _handle_invoice_paid(db, invoice_obj: dict) -> None:
    """invoice.paid → atualizar BillingSubscription e criar/atualizar BillingInvoice."""
    from app.models.product import BillingInvoice, BillingSubscription
    import uuid

    stripe_sub_id = invoice_obj.get("subscription", "")
    stripe_inv_id = invoice_obj.get("id", "")
    amount_paid = invoice_obj.get("amount_paid", 0) / 100
    period_start_ts = invoice_obj.get("period_start")
    period_end_ts = invoice_obj.get("period_end")
    invoice_pdf_url = invoice_obj.get("invoice_pdf", "")
    customer_id = invoice_obj.get("customer", "")

    # Update subscription status
    sub = None
    if stripe_sub_id:
        sub_result = await db.execute(
            select(BillingSubscription).where(BillingSubscription.stripe_subscription_id == stripe_sub_id)
        )
        sub = sub_result.scalar_one_or_none()
        if sub:
            sub.status = "active"

    # Find or create invoice record
    if stripe_inv_id:
        inv_result = await db.execute(
            select(BillingInvoice).where(BillingInvoice.stripe_invoice_id == stripe_inv_id)
        )
        inv = inv_result.scalar_one_or_none()

        tenant_id = sub.tenant_id if sub else None
        subscription_id = sub.id if sub else None

        if inv:
            inv.status = "paid"
            inv.paid_at = datetime.now(timezone.utc)
            inv.amount_brl = amount_paid
            if invoice_pdf_url:
                inv.invoice_pdf_url = invoice_pdf_url
        elif tenant_id:
            period_start = datetime.fromtimestamp(period_start_ts, tz=timezone.utc) if period_start_ts else None
            period_end = datetime.fromtimestamp(period_end_ts, tz=timezone.utc) if period_end_ts else None

            inv = BillingInvoice(
                tenant_id=tenant_id,
                subscription_id=subscription_id,
                stripe_invoice_id=stripe_inv_id,
                amount_brl=amount_paid,
                status="paid",
                period_start=period_start,
                period_end=period_end,
                paid_at=datetime.now(timezone.utc),
                invoice_pdf_url=invoice_pdf_url or None,
            )
            db.add(inv)

    await db.flush()


async def _handle_payment_failed(db, invoice_obj: dict) -> None:
    """invoice.payment_failed → status past_due + criar BillingInvoice status=open."""
    from app.models.product import BillingSubscription, BillingInvoice

    stripe_sub_id = invoice_obj.get("subscription", "")
    stripe_inv_id = invoice_obj.get("id", "")
    amount_due = invoice_obj.get("amount_due", 0) / 100
    period_start_ts = invoice_obj.get("period_start")
    period_end_ts = invoice_obj.get("period_end")

    sub = None
    if stripe_sub_id:
        sub_result = await db.execute(
            select(BillingSubscription).where(BillingSubscription.stripe_subscription_id == stripe_sub_id)
        )
        sub = sub_result.scalar_one_or_none()
        if sub:
            sub.status = "past_due"

    # Create or update invoice with open status
    if stripe_inv_id and sub:
        inv_result = await db.execute(
            select(BillingInvoice).where(BillingInvoice.stripe_invoice_id == stripe_inv_id)
        )
        inv = inv_result.scalar_one_or_none()

        if not inv:
            period_start = datetime.fromtimestamp(period_start_ts, tz=timezone.utc) if period_start_ts else None
            period_end = datetime.fromtimestamp(period_end_ts, tz=timezone.utc) if period_end_ts else None

            inv = BillingInvoice(
                tenant_id=sub.tenant_id,
                subscription_id=sub.id,
                stripe_invoice_id=stripe_inv_id,
                amount_brl=amount_due,
                status="open",
                period_start=period_start,
                period_end=period_end,
            )
            db.add(inv)
        else:
            inv.status = "open"

    await db.flush()


async def _handle_subscription_change(db, sub_obj: dict, event_type: str) -> None:
    """customer.subscription.updated/deleted → atualizar BillingSubscription."""
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

    await db.flush()
