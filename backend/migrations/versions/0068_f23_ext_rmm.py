"""F23.ext — RMM Integrations: NinjaRMM, Atera, ConnectWise Automate, Tactical RMM.

Revision ID: 0068
Revises: 0067
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

revision = "0068"
down_revision = "0067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rmm_integrations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("rmm_type", sa.String(30), nullable=False),
        sa.Column("base_url", sa.Text, nullable=False),
        sa.Column("config_encrypted", sa.Text, nullable=True),
        sa.Column("verify_ssl", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_sync_status", sa.String(20), nullable=True),
        sa.Column("last_sync_message", sa.Text, nullable=True),
        sa.Column("agent_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "rmm_agents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("integration_id", UUID(as_uuid=True), sa.ForeignKey("rmm_integrations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("external_id", sa.String(200), nullable=False),
        sa.Column("hostname", sa.String(200), nullable=False),
        sa.Column("os_name", sa.Text, nullable=True),
        sa.Column("ip_address", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
        sa.Column("patches_pending", sa.Integer, nullable=True),
        sa.Column("alerts_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("raw_data", JSONB, nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint(
        "uq_rmm_agents_integration_external",
        "rmm_agents",
        ["integration_id", "external_id"],
    )


def downgrade() -> None:
    op.drop_table("rmm_agents")
    op.drop_table("rmm_integrations")
