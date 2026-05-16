"""
Integração Stripe — criação de customers, subscriptions e checkout sessions.
Requer variável de ambiente STRIPE_SECRET_KEY.
"""
from __future__ import annotations

import stripe
from app.config import settings

stripe.api_key = getattr(settings, "stripe_secret_key", "")


async def get_or_create_customer(db, tenant) -> str:
    """Retorna stripe_customer_id existente ou cria novo Customer no Stripe."""
    from sqlalchemy import select
    from app.models.product import BillingSubscription

    result = await db.execute(
        select(BillingSubscription).where(BillingSubscription.tenant_id == tenant.id)
    )
    sub = result.scalar_one_or_none()

    if sub and getattr(sub, "stripe_customer_id", None):
        return sub.stripe_customer_id

    customer = stripe.Customer.create(
        name=tenant.name,
        metadata={"tenant_id": str(tenant.id), "tenant_slug": tenant.slug},
    )
    return customer.id


async def create_checkout_session(
    db,
    tenant,
    plan,  # BillingPlan ORM object
    success_url: str,
    cancel_url: str,
) -> str:
    """Cria Stripe Checkout Session e retorna URL de redirect."""
    customer_id = await get_or_create_customer(db, tenant)

    # Criar preço Stripe inline (cents BRL)
    price_cents = int(plan.monthly_price_brl * 100)

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "brl",
                "product_data": {
                    "name": plan.name,
                    "description": (
                        f"Eternity SecOps {plan.name} — "
                        f"{plan.max_devices or 'ilimitados'} devices, "
                        f"{plan.max_users or 'ilimitados'} usuários"
                    ),
                },
                "unit_amount": price_cents,
                "recurring": {"interval": "month"},
            },
            "quantity": 1,
        }],
        mode="subscription",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"tenant_id": str(tenant.id), "plan_id": str(plan.id)},
    )
    return session.url


async def cancel_subscription(stripe_subscription_id: str) -> None:
    """Cancela assinatura Stripe no final do período."""
    stripe.Subscription.modify(
        stripe_subscription_id,
        cancel_at_period_end=True,
    )


async def get_invoices(stripe_customer_id: str, limit: int = 10) -> list[dict]:
    """Lista faturas do Stripe para um customer."""
    invoices = stripe.Invoice.list(customer=stripe_customer_id, limit=limit)
    return [
        {
            "stripe_invoice_id": inv.id,
            "amount_brl": inv.amount_paid / 100,
            "status": inv.status,
            "paid_at": inv.status_transitions.paid_at,
            "invoice_pdf": inv.invoice_pdf,
            "period_start": inv.period_start,
            "period_end": inv.period_end,
        }
        for inv in invoices.data
    ]
