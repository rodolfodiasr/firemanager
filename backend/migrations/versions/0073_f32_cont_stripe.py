"""F32.cont — Stripe billing: campos stripe_customer_id, stripe_subscription_id e webhook events.

Revision ID: 0073
Revises: 0072
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

revision = "0073"
down_revision = "0072"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("billing_subscriptions", sa.Column("stripe_customer_id", sa.String(100), nullable=True))
    op.add_column("billing_subscriptions", sa.Column("stripe_subscription_id", sa.String(100), nullable=True))
    op.add_column("billing_subscriptions", sa.Column("stripe_price_id", sa.String(100), nullable=True))

    op.add_column("billing_invoices", sa.Column("stripe_invoice_id", sa.String(100), nullable=True))
    op.add_column("billing_invoices", sa.Column("stripe_payment_intent", sa.String(100), nullable=True))
    op.add_column("billing_invoices", sa.Column("payment_url", sa.Text, nullable=True))

    op.create_table(
        "stripe_webhook_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("stripe_event_id", sa.String(100), nullable=False, unique=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=True),
        sa.Column("payload", JSONB, nullable=True),
        sa.Column("processed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("stripe_webhook_events")
    op.drop_column("billing_invoices", "payment_url")
    op.drop_column("billing_invoices", "stripe_payment_intent")
    op.drop_column("billing_invoices", "stripe_invoice_id")
    op.drop_column("billing_subscriptions", "stripe_price_id")
    op.drop_column("billing_subscriptions", "stripe_subscription_id")
    op.drop_column("billing_subscriptions", "stripe_customer_id")
