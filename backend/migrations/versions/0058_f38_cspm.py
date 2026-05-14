"""F38 — Cloud Security Posture Management (CSPM)."""
from alembic import op

revision = "0058"
down_revision = "0057"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS cloud_accounts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            provider VARCHAR(20) NOT NULL,
            credentials_encrypted TEXT,
            region VARCHAR(50),
            is_active BOOLEAN NOT NULL DEFAULT true,
            last_sync_at TIMESTAMPTZ,
            last_sync_status VARCHAR(20),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_cloud_accounts_tenant_id ON cloud_accounts(tenant_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS cloud_security_findings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            account_id UUID NOT NULL REFERENCES cloud_accounts(id) ON DELETE CASCADE,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            resource_type VARCHAR(50) NOT NULL,
            resource_id TEXT NOT NULL,
            resource_name TEXT,
            check_id VARCHAR(80) NOT NULL,
            check_title TEXT NOT NULL,
            severity VARCHAR(20) NOT NULL DEFAULT 'medium',
            status VARCHAR(20) NOT NULL DEFAULT 'open',
            details JSONB,
            detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            resolved_at TIMESTAMPTZ,
            accepted_by UUID,
            accepted_reason TEXT,
            UNIQUE (account_id, resource_id, check_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_cloud_findings_tenant_id ON cloud_security_findings(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_cloud_findings_account_id ON cloud_security_findings(account_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS cloud_resources (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            account_id UUID NOT NULL REFERENCES cloud_accounts(id) ON DELETE CASCADE,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            resource_type VARCHAR(50) NOT NULL,
            resource_id TEXT NOT NULL,
            resource_name TEXT,
            region VARCHAR(50),
            rules JSONB,
            tags JSONB,
            risk_score INTEGER,
            synced_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_cloud_resources_tenant_id ON cloud_resources(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_cloud_resources_account_id ON cloud_resources(account_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS cloud_resources")
    op.execute("DROP TABLE IF EXISTS cloud_security_findings")
    op.execute("DROP TABLE IF EXISTS cloud_accounts")
