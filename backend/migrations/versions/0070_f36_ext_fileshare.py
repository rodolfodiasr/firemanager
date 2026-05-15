"""F36.ext — File Share Governance: auditoria de pastas compartilhadas AD.

Revision ID: 0070
Revises: 0069
"""
from alembic import op

revision = "0070"
down_revision = "0069"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS file_share_configs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(200) NOT NULL,
            server_hostname VARCHAR(200) NOT NULL,
            unc_root VARCHAR(500) NOT NULL,
            edge_agent_id UUID REFERENCES edge_agents(id) ON DELETE SET NULL,
            config_encrypted TEXT,
            scan_depth INTEGER NOT NULL DEFAULT 2,
            is_active BOOLEAN NOT NULL DEFAULT true,
            last_scan_at TIMESTAMPTZ,
            last_scan_status VARCHAR(20),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_file_share_configs_tenant_id ON file_share_configs(tenant_id)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS file_share_shares (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            config_id UUID NOT NULL REFERENCES file_share_configs(id) ON DELETE CASCADE,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            share_name VARCHAR(200) NOT NULL,
            unc_path VARCHAR(500) NOT NULL,
            description TEXT,
            abe_enabled BOOLEAN,
            health_status VARCHAR(20) NOT NULL DEFAULT 'unknown',
            health_issues JSONB,
            acl_count INTEGER NOT NULL DEFAULT 0,
            scanned_at TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_file_share_shares_config_id ON file_share_shares(config_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_file_share_shares_tenant_id ON file_share_shares(tenant_id)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS file_share_acl_entries (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            share_id UUID NOT NULL REFERENCES file_share_shares(id) ON DELETE CASCADE,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            folder_path TEXT NOT NULL,
            principal_name VARCHAR(300) NOT NULL,
            principal_type VARCHAR(20) NOT NULL DEFAULT 'unknown',
            permission_type VARCHAR(50) NOT NULL,
            inherited BOOLEAN NOT NULL DEFAULT false,
            is_deny BOOLEAN NOT NULL DEFAULT false,
            depth INTEGER NOT NULL DEFAULT 0,
            scanned_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_file_share_acl_entries_share_id ON file_share_acl_entries(share_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_file_share_acl_entries_tenant_id ON file_share_acl_entries(tenant_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS file_share_acl_entries")
    op.execute("DROP TABLE IF EXISTS file_share_shares")
    op.execute("DROP TABLE IF EXISTS file_share_configs")
