"""F37 — SIEM connectors + normalized alerts."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "siem_connectors",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", PG_UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("siem_type", sa.String(30), nullable=False),
        sa.Column("base_url", sa.Text, nullable=False),
        sa.Column("config_encrypted", sa.Text, nullable=True),
        sa.Column("webhook_secret", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_event_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_siem_connectors_tenant_id", "siem_connectors", ["tenant_id"])

    op.create_table(
        "siem_alerts",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", PG_UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("connector_id", PG_UUID(as_uuid=True), sa.ForeignKey("siem_connectors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_rule_id", sa.Text, nullable=True),
        sa.Column("severity", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("affected_host", sa.Text, nullable=True),
        sa.Column("source_ip", sa.Text, nullable=True),
        sa.Column("raw_payload", JSONB, nullable=True),
        sa.Column("normalized_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("playbook_triggered", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("playbook_execution_id", PG_UUID(as_uuid=True), nullable=True),
    )
    op.create_index("ix_siem_alerts_tenant_id", "siem_alerts", ["tenant_id"])
    op.create_index("ix_siem_alerts_tenant_normalized_at", "siem_alerts", ["tenant_id", "normalized_at"])


def downgrade() -> None:
    op.drop_index("ix_siem_alerts_tenant_normalized_at", table_name="siem_alerts")
    op.drop_index("ix_siem_alerts_tenant_id", table_name="siem_alerts")
    op.drop_table("siem_alerts")
    op.drop_index("ix_siem_connectors_tenant_id", table_name="siem_connectors")
    op.drop_table("siem_connectors")
