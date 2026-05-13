"""F32 — Produto: Billing, Planos, Onboarding Wizard, Help Center, i18n.

Revision ID: 0066
Revises: 0065
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

revision = "0066"
down_revision = "0065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "billing_plans",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
        sa.Column("slug", sa.String(30), nullable=False, unique=True),
        sa.Column("monthly_price_brl", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("max_devices", sa.Integer, nullable=True),
        sa.Column("max_users", sa.Integer, nullable=True),
        sa.Column("ai_token_quota", sa.Integer, nullable=True),
        sa.Column("sla_target_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("features", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "billing_subscriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("plan_id", UUID(as_uuid=True), sa.ForeignKey("billing_plans.id"), nullable=False),
        sa.Column("stripe_customer_id", sa.String(200), nullable=True),
        sa.Column("stripe_subscription_id", sa.String(200), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("current_period_start", sa.DateTime, nullable=True),
        sa.Column("current_period_end", sa.DateTime, nullable=True),
        sa.Column("cancel_at_period_end", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("trial_end", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_billing_subscriptions_tenant_id", "billing_subscriptions", ["tenant_id"])

    op.create_table(
        "billing_invoices",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("subscription_id", UUID(as_uuid=True), sa.ForeignKey("billing_subscriptions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("stripe_invoice_id", sa.String(200), nullable=True, unique=True),
        sa.Column("amount_brl", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("period_start", sa.DateTime, nullable=True),
        sa.Column("period_end", sa.DateTime, nullable=True),
        sa.Column("paid_at", sa.DateTime, nullable=True),
        sa.Column("due_date", sa.DateTime, nullable=True),
        sa.Column("invoice_pdf_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index("ix_billing_invoices_tenant_id", "billing_invoices", ["tenant_id"])

    op.create_table(
        "onboarding_checklists",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("step_add_device", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("step_run_snapshot", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("step_ask_agent", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("step_configure_alert", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("completed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("skipped", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("completed_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "user_id", name="uq_onboarding_tenant_user"),
    )
    op.create_index("ix_onboarding_checklists_tenant_id", "onboarding_checklists", ["tenant_id"])

    op.create_table(
        "help_articles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("slug", sa.String(200), nullable=False, unique=True),
        sa.Column("category", sa.String(50), nullable=False, server_default="general"),
        sa.Column("persona", sa.String(30), nullable=True),
        sa.Column("content_md", sa.Text, nullable=False),
        sa.Column("is_published", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("view_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "user_preferences",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("language", sa.String(10), nullable=False, server_default="pt-BR"),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="America/Sao_Paulo"),
        sa.Column("theme", sa.String(20), nullable=False, server_default="dark"),
        sa.Column("notifications_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("onboarding_step", sa.Integer, nullable=False, server_default="0"),
        sa.Column("onboarding_completed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("extra", JSONB, nullable=True),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("user_preferences")
    op.drop_table("help_articles")
    op.drop_table("onboarding_checklists")
    op.drop_table("billing_invoices")
    op.drop_table("billing_subscriptions")
    op.drop_table("billing_plans")
