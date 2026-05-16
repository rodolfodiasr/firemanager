"""F33 — SIRP: security_incidents (registro de incidentes de segurança).

Revision ID: 0083
Revises: 0082
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY

revision = "0083"
down_revision = "0082"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "security_incidents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("severity", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("category", sa.String(50), nullable=False, server_default="other"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("reported_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assigned_to", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("affected_systems", ARRAY(sa.Text), nullable=True),
        sa.Column("timeline", JSONB, nullable=False, server_default="[]"),
        sa.Column("root_cause", sa.Text, nullable=True),
        sa.Column("remediation", sa.Text, nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_security_incidents_tenant_id", "security_incidents", ["tenant_id"])
    op.create_index("ix_security_incidents_tenant_status", "security_incidents", ["tenant_id", "status"])
    op.create_index("ix_security_incidents_severity", "security_incidents", ["tenant_id", "severity"])


def downgrade() -> None:
    op.drop_table("security_incidents")
