"""0092 — remediation: origin tracking, templates, campaigns; server_id nullable.

Revision ID: 0092
Revises: 0091
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "0092"
down_revision = "0091"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Tabela de templates reutilizáveis ─────────────────────────────────────
    op.create_table(
        "remediation_templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("vendor", sa.String(50), nullable=True),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("commands", JSONB, nullable=False, server_default="[]"),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )

    # ── Tabela de campanhas (1 template → N devices) ──────────────────────────
    op.create_table(
        "remediation_campaigns",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True),
                  sa.ForeignKey("tenants.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("template_id", UUID(as_uuid=True),
                  sa.ForeignKey("remediation_templates.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("origin_type", sa.String(50), nullable=True),
        sa.Column("origin_ref", sa.String(500), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True),
                  server_default=sa.text("now()"), nullable=False),
    )

    # ── Alterações em remediation_plans ───────────────────────────────────────
    # server_id passa a ser nullable (remediações de GLPI/SOAR/alertas não têm server)
    op.alter_column("remediation_plans", "server_id", nullable=True)

    op.add_column("remediation_plans",
                  sa.Column("origin_type", sa.String(50), nullable=True))
    op.add_column("remediation_plans",
                  sa.Column("origin_ref", sa.String(500), nullable=True))
    op.add_column("remediation_plans",
                  sa.Column("campaign_id", UUID(as_uuid=True),
                            sa.ForeignKey("remediation_campaigns.id", ondelete="SET NULL"),
                            nullable=True))


def downgrade() -> None:
    op.drop_column("remediation_plans", "campaign_id")
    op.drop_column("remediation_plans", "origin_ref")
    op.drop_column("remediation_plans", "origin_type")
    op.alter_column("remediation_plans", "server_id", nullable=False)
    op.drop_table("remediation_campaigns")
    op.drop_table("remediation_templates")
