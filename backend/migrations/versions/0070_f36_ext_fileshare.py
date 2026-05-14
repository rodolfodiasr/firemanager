"""F36.ext — File Share Governance: auditoria de pastas compartilhadas AD.

Revision ID: 0070
Revises: 0069
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

revision = "0070"
down_revision = "0069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "file_share_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("server_hostname", sa.String(200), nullable=False),
        sa.Column("unc_root", sa.String(500), nullable=False),
        sa.Column("edge_agent_id", UUID(as_uuid=True), sa.ForeignKey("edge_agents.id", ondelete="SET NULL"), nullable=True),
        sa.Column("config_encrypted", sa.Text, nullable=True),
        sa.Column("scan_depth", sa.Integer, nullable=False, server_default="2"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_scan_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_scan_status", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "file_share_shares",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("config_id", UUID(as_uuid=True), sa.ForeignKey("file_share_configs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("share_name", sa.String(200), nullable=False),
        sa.Column("unc_path", sa.String(500), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("abe_enabled", sa.Boolean, nullable=True),
        sa.Column("health_status", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("health_issues", JSONB, nullable=True),
        sa.Column("acl_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "file_share_acl_entries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("share_id", UUID(as_uuid=True), sa.ForeignKey("file_share_shares.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("folder_path", sa.Text, nullable=False),
        sa.Column("principal_name", sa.String(300), nullable=False),
        sa.Column("principal_type", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("permission_type", sa.String(50), nullable=False),
        sa.Column("inherited", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_deny", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("depth", sa.Integer, nullable=False, server_default="0"),
        sa.Column("scanned_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("file_share_acl_entries")
    op.drop_table("file_share_shares")
    op.drop_table("file_share_configs")
