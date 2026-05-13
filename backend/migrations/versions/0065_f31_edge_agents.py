"""F31 — Edge Agents, SSO/OIDC, Marketplace, RBAC granular.

Revision ID: 0065
Revises: 0064
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
import uuid

revision = "0065"
down_revision = "0064"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "edge_agents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("device_ids", JSONB, nullable=True),
        sa.Column("version", sa.String(30), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="offline"),
        sa.Column("last_seen", sa.DateTime, nullable=True),
        sa.Column("ip_address", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_edge_agents_tenant_id", "edge_agents", ["tenant_id"])

    op.create_table(
        "sso_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("provider", sa.String(30), nullable=False, server_default="azure_ad"),
        sa.Column("client_id", sa.String(200), nullable=False),
        sa.Column("client_secret_encrypted", sa.Text, nullable=True),
        sa.Column("discovery_url", sa.String(500), nullable=False),
        sa.Column("group_claim", sa.String(100), nullable=True, server_default="groups"),
        sa.Column("group_mapping", JSONB, nullable=True),
        sa.Column("sso_required", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_sso_configs_tenant_id", "sso_configs", ["tenant_id"])

    op.create_table(
        "marketplace_plugins",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("version", sa.String(30), nullable=False),
        sa.Column("author_tenant_id", UUID(as_uuid=True), nullable=True),
        sa.Column("category", sa.String(50), nullable=False, server_default="connector"),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("package_url", sa.String(500), nullable=True),
        sa.Column("signature", sa.String(200), nullable=True),
        sa.Column("approved_at", sa.DateTime, nullable=True),
        sa.Column("approved_by", UUID(as_uuid=True), nullable=True),
        sa.Column("is_builtin", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("download_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "tenant_plugins",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("plugin_id", UUID(as_uuid=True), sa.ForeignKey("marketplace_plugins.id", ondelete="CASCADE"), nullable=False),
        sa.Column("installed_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("installed_by", UUID(as_uuid=True), nullable=True),
        sa.Column("config", JSONB, nullable=True),
        sa.UniqueConstraint("tenant_id", "plugin_id", name="uq_tenant_plugins"),
    )
    op.create_index("ix_tenant_plugins_tenant_id", "tenant_plugins", ["tenant_id"])

    op.create_table(
        "rbac_custom_roles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("permissions", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "name", name="uq_rbac_roles_tenant_name"),
    )
    op.create_index("ix_rbac_custom_roles_tenant_id", "rbac_custom_roles", ["tenant_id"])

    op.create_table(
        "rbac_role_assignments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("role_id", UUID(as_uuid=True), sa.ForeignKey("rbac_custom_roles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assigned_by", UUID(as_uuid=True), nullable=True),
        sa.Column("assigned_at", sa.DateTime, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "user_id", "role_id", name="uq_rbac_assignments"),
    )
    op.create_index("ix_rbac_role_assignments_tenant_id", "rbac_role_assignments", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("rbac_role_assignments")
    op.drop_table("rbac_custom_roles")
    op.drop_table("tenant_plugins")
    op.drop_table("marketplace_plugins")
    op.drop_table("sso_configs")
    op.drop_table("edge_agents")
