"""F37.ext — SIEM Syslog Configs: CEF forwarder universal para qualquer SIEM.

Revision ID: 0071
Revises: 0070
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

revision = "0071"
down_revision = "0070"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "siem_syslog_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("target_host", sa.String(300), nullable=False),
        sa.Column("target_port", sa.Integer, nullable=False, server_default="514"),
        sa.Column("protocol", sa.String(10), nullable=False, server_default="tcp"),
        sa.Column("tls_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("tls_verify", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("facility", sa.Integer, nullable=False, server_default="1"),
        sa.Column("min_severity", sa.String(20), nullable=False, server_default="low"),
        sa.Column("event_types", JSONB, nullable=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_forward_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("events_forwarded", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("siem_syslog_configs")
