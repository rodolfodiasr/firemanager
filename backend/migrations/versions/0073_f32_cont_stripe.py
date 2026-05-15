"""F32.cont — Stripe billing: campos stripe_customer_id, stripe_subscription_id e webhook events.

Revision ID: 0073
Revises: 0072
"""
from alembic import op

revision = "0073"
down_revision = "0072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE billing_subscriptions ADD COLUMN IF NOT EXISTS stripe_customer_id VARCHAR(100)")
    op.execute("ALTER TABLE billing_subscriptions ADD COLUMN IF NOT EXISTS stripe_subscription_id VARCHAR(100)")
    op.execute("ALTER TABLE billing_subscriptions ADD COLUMN IF NOT EXISTS stripe_price_id VARCHAR(100)")

    op.execute("ALTER TABLE billing_invoices ADD COLUMN IF NOT EXISTS stripe_invoice_id VARCHAR(100)")
    op.execute("ALTER TABLE billing_invoices ADD COLUMN IF NOT EXISTS stripe_payment_intent VARCHAR(100)")
    op.execute("ALTER TABLE billing_invoices ADD COLUMN IF NOT EXISTS payment_url TEXT")

    op.execute("""
        CREATE TABLE IF NOT EXISTS stripe_webhook_events (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            stripe_event_id VARCHAR(100) NOT NULL UNIQUE,
            event_type VARCHAR(100) NOT NULL,
            tenant_id UUID,
            payload JSONB,
            processed BOOLEAN NOT NULL DEFAULT false,
            error TEXT,
            received_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            processed_at TIMESTAMPTZ
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS stripe_webhook_events")
    op.execute("ALTER TABLE billing_invoices DROP COLUMN IF EXISTS payment_url")
    op.execute("ALTER TABLE billing_invoices DROP COLUMN IF EXISTS stripe_payment_intent")
    op.execute("ALTER TABLE billing_invoices DROP COLUMN IF EXISTS stripe_invoice_id")
    op.execute("ALTER TABLE billing_subscriptions DROP COLUMN IF EXISTS stripe_price_id")
    op.execute("ALTER TABLE billing_subscriptions DROP COLUMN IF EXISTS stripe_subscription_id")
    op.execute("ALTER TABLE billing_subscriptions DROP COLUMN IF EXISTS stripe_customer_id")
