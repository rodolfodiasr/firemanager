"""F28.1 — DLP: Prevenção de Perda de Dados no chat.

Tabelas:
  dlp_configs   — configuração global DLP por tenant
  dlp_rules     — regras por tenant (builtin + custom)
  dlp_incidents — log de incidentes (sem dado original)

Revision ID: 0067
Revises: 0066
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

revision = "0067"
down_revision = "0066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dlp_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("compliance_mode", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("incident_threshold_count", sa.Integer, nullable=False, server_default="5"),
        sa.Column("incident_threshold_hours", sa.Integer, nullable=False, server_default="24"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    op.create_table(
        "dlp_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_key", sa.String(64), nullable=False),
        sa.Column("rule_name", sa.String(100), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("action", sa.String(8), nullable=False, server_default="block"),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_builtin", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("pattern", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "rule_key", name="uq_dlp_rules_tenant_key"),
    )

    op.create_index("ix_dlp_rules_tenant_id", "dlp_rules", ["tenant_id"])

    op.create_table(
        "dlp_incidents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("pii_type", sa.String(64), nullable=False),
        sa.Column("action_taken", sa.String(8), nullable=False),
        sa.Column("source", sa.String(32), nullable=False, server_default="chat"),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_index("ix_dlp_incidents_tenant_id", "dlp_incidents", ["tenant_id"])
    op.create_index("ix_dlp_incidents_created_at", "dlp_incidents", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_dlp_incidents_created_at", "dlp_incidents")
    op.drop_index("ix_dlp_incidents_tenant_id", "dlp_incidents")
    op.drop_table("dlp_incidents")
    op.drop_index("ix_dlp_rules_tenant_id", "dlp_rules")
    op.drop_table("dlp_rules")
    op.drop_table("dlp_configs")
