"""F31.cont — SSO Role Mappings: mapeamento grupo IdP → role plataforma + JIT provisioning.

Revision ID: 0069
Revises: 0068
"""
from alembic import op

revision = "0069"
down_revision = "0068"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS sso_role_mappings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            sso_config_id UUID NOT NULL,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            external_group VARCHAR(300) NOT NULL,
            platform_role VARCHAR(50) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (sso_config_id, external_group)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_sso_role_mappings_sso_config_id ON sso_role_mappings(sso_config_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sso_role_mappings_tenant_id ON sso_role_mappings(tenant_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS sso_role_mappings")
