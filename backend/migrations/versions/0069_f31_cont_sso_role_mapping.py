"""F31.cont — SSO Role Mappings: mapeamento grupo IdP → role plataforma + JIT provisioning.

Revision ID: 0069
Revises: 0068
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

revision = "0069"
down_revision = "0068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sso_role_mappings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("sso_config_id", UUID(as_uuid=True), sa.ForeignKey("sso_configs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("external_group", sa.String(300), nullable=False),
        sa.Column("platform_role", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_unique_constraint(
        "uq_sso_role_mapping_group",
        "sso_role_mappings",
        ["sso_config_id", "external_group"],
    )


def downgrade() -> None:
    op.drop_table("sso_role_mappings")
