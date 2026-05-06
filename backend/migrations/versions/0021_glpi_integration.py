"""GLPI integration: per-tenant config and ticket analysis tracking

Revision ID: 0021
Revises: 0020
Create Date: 2026-05-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "glpi_integrations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("glpi_url", sa.String(500), nullable=False),
        sa.Column("app_token", sa.String(200), nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("encrypted_password", sa.Text, nullable=False),
        sa.Column("verify_ssl", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("min_priority", sa.Integer, nullable=False, server_default="3"),
        sa.Column("trigger_types", postgresql.JSONB, nullable=False, server_default="[1, 2]"),
        sa.Column("trigger_categories", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("tag_analyzed", sa.String(100), nullable=False, server_default="fm-analyzed"),
        sa.Column("poll_interval_minutes", sa.Integer, nullable=False, server_default="5"),
        sa.Column("lookback_hours", sa.Integer, nullable=False, server_default="24"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_glpi_integrations_tenant_id", "glpi_integrations", ["tenant_id"])
    op.create_unique_constraint("uq_glpi_integrations_tenant", "glpi_integrations", ["tenant_id"])

    op.create_table(
        "glpi_ticket_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("glpi_integration_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("glpi_ticket_id", sa.Integer, nullable=False),
        sa.Column("glpi_ticket_title", sa.String(500), nullable=False, server_default=""),
        sa.Column("glpi_ticket_content", sa.Text, nullable=True),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("diagnostico", sa.Text, nullable=True),
        sa.Column("acoes_imediatas", sa.Text, nullable=True),
        sa.Column("plano_remediacao", sa.Text, nullable=True),
        sa.Column("causa_raiz", sa.Text, nullable=True),
        sa.Column("prevencao", sa.Text, nullable=True),
        sa.Column("confianca", sa.Float, nullable=True),
        sa.Column("is_security_incident", sa.Boolean, nullable=True),
        sa.Column("is_recurrent", sa.Boolean, nullable=True),
        sa.Column("recurrence_count", sa.Integer, nullable=True),
        sa.Column("related_ticket_ids", postgresql.JSONB, nullable=True),
        sa.Column("glpi_followup_id", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_glpi_ticket_analyses_tenant_id", "glpi_ticket_analyses", ["tenant_id"])
    op.create_index("ix_glpi_ticket_analyses_ticket_id", "glpi_ticket_analyses", ["glpi_ticket_id"])
    op.create_index("ix_glpi_ticket_analyses_status", "glpi_ticket_analyses", ["status"])
    op.create_unique_constraint(
        "uq_glpi_analyses_tenant_ticket",
        "glpi_ticket_analyses",
        ["tenant_id", "glpi_ticket_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_glpi_analyses_tenant_ticket", "glpi_ticket_analyses", type_="unique")
    op.drop_index("ix_glpi_ticket_analyses_status", table_name="glpi_ticket_analyses")
    op.drop_index("ix_glpi_ticket_analyses_ticket_id", table_name="glpi_ticket_analyses")
    op.drop_index("ix_glpi_ticket_analyses_tenant_id", table_name="glpi_ticket_analyses")
    op.drop_table("glpi_ticket_analyses")

    op.drop_constraint("uq_glpi_integrations_tenant", "glpi_integrations", type_="unique")
    op.drop_index("ix_glpi_integrations_tenant_id", table_name="glpi_integrations")
    op.drop_table("glpi_integrations")
