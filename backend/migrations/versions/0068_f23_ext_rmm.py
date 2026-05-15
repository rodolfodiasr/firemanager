"""F23.ext — RMM Integrations: NinjaRMM, Atera, ConnectWise Automate, Tactical RMM.

Revision ID: 0068
Revises: 0067
"""
from alembic import op

revision = "0068"
down_revision = "0067"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS rmm_integrations (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(200) NOT NULL,
            rmm_type VARCHAR(30) NOT NULL,
            base_url TEXT NOT NULL,
            config_encrypted TEXT,
            verify_ssl BOOLEAN NOT NULL DEFAULT true,
            is_active BOOLEAN NOT NULL DEFAULT true,
            last_sync_at TIMESTAMPTZ,
            last_sync_status VARCHAR(20),
            last_sync_message TEXT,
            agent_count INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_rmm_integrations_tenant_id ON rmm_integrations(tenant_id)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS rmm_agents (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            integration_id UUID NOT NULL REFERENCES rmm_integrations(id) ON DELETE CASCADE,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            external_id VARCHAR(200) NOT NULL,
            hostname VARCHAR(200) NOT NULL,
            os_name TEXT,
            ip_address VARCHAR(50),
            status VARCHAR(20) NOT NULL DEFAULT 'unknown',
            last_seen TIMESTAMPTZ,
            patches_pending INTEGER,
            alerts_count INTEGER NOT NULL DEFAULT 0,
            raw_data JSONB,
            synced_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (integration_id, external_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_rmm_agents_integration_id ON rmm_agents(integration_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_rmm_agents_tenant_id ON rmm_agents(tenant_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS rmm_agents")
    op.execute("DROP TABLE IF EXISTS rmm_integrations")
