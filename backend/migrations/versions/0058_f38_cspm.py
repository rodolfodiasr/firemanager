"""F38 — Cloud Security Posture Management (CSPM)."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID

revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cloud_accounts",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", PG_UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),   # aws | azure | gcp
        sa.Column("credentials_encrypted", sa.Text, nullable=True),
        sa.Column("region", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_sync_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_sync_status", sa.String(20), nullable=True),  # ok | error | syncing
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_cloud_accounts_tenant_id", "cloud_accounts", ["tenant_id"])

    op.create_table(
        "cloud_security_findings",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", PG_UUID(as_uuid=True), sa.ForeignKey("cloud_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", PG_UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),   # security_group | nsg | gcp_fw_rule
        sa.Column("resource_id", sa.Text, nullable=False),
        sa.Column("resource_name", sa.Text, nullable=True),
        sa.Column("check_id", sa.String(80), nullable=False),        # e.g. "sg-ssh-open-world"
        sa.Column("check_title", sa.Text, nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),   # open | accepted | resolved
        sa.Column("details", JSONB, nullable=True),
        sa.Column("detected_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("accepted_by", PG_UUID(as_uuid=True), nullable=True),
        sa.Column("accepted_reason", sa.Text, nullable=True),
    )
    op.create_index("ix_cloud_findings_tenant_id", "cloud_security_findings", ["tenant_id"])
    op.create_index("ix_cloud_findings_account_id", "cloud_security_findings", ["account_id"])
    op.create_index(
        "uq_cloud_findings_resource_check",
        "cloud_security_findings",
        ["account_id", "resource_id", "check_id"],
        unique=True,
    )

    op.create_table(
        "cloud_resources",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("account_id", PG_UUID(as_uuid=True), sa.ForeignKey("cloud_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", PG_UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", sa.Text, nullable=False),
        sa.Column("resource_name", sa.Text, nullable=True),
        sa.Column("region", sa.String(50), nullable=True),
        sa.Column("rules", JSONB, nullable=True),     # inbound/outbound rules normalized
        sa.Column("tags", JSONB, nullable=True),
        sa.Column("risk_score", sa.Integer, nullable=True),
        sa.Column("synced_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_cloud_resources_tenant_id", "cloud_resources", ["tenant_id"])
    op.create_index("ix_cloud_resources_account_id", "cloud_resources", ["account_id"])


def downgrade() -> None:
    op.drop_index("ix_cloud_resources_account_id", table_name="cloud_resources")
    op.drop_index("ix_cloud_resources_tenant_id", table_name="cloud_resources")
    op.drop_table("cloud_resources")
    op.drop_index("uq_cloud_findings_resource_check", table_name="cloud_security_findings")
    op.drop_index("ix_cloud_findings_account_id", table_name="cloud_security_findings")
    op.drop_index("ix_cloud_findings_tenant_id", table_name="cloud_security_findings")
    op.drop_table("cloud_security_findings")
    op.drop_index("ix_cloud_accounts_tenant_id", table_name="cloud_accounts")
    op.drop_table("cloud_accounts")
