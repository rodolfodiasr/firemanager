"""web_audit: auditoria de navegação web por estação AD

Revision ID: 0082
Revises: 0081
"""
from alembic import op

revision = "0082"
down_revision = "0081"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS web_audit_configs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL UNIQUE REFERENCES tenants(id) ON DELETE CASCADE,
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            collection_method VARCHAR(30) NOT NULL DEFAULT 'agent',
            gpo_share_path TEXT,
            poll_interval_minutes INTEGER NOT NULL DEFAULT 60,
            retention_days INTEGER NOT NULL DEFAULT 90,
            alert_on_malicious BOOLEAN NOT NULL DEFAULT TRUE,
            alert_on_shadow_it BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)

    op.execute("""
        CREATE TABLE IF NOT EXISTS web_audit_entries (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            config_id UUID NOT NULL REFERENCES web_audit_configs(id) ON DELETE CASCADE,
            workstation VARCHAR(255) NOT NULL,
            ad_user VARCHAR(255),
            department VARCHAR(255),
            url TEXT NOT NULL,
            domain VARCHAR(255) NOT NULL,
            visited_at TIMESTAMPTZ NOT NULL,
            browser VARCHAR(50),
            title TEXT,
            visit_count INTEGER NOT NULL DEFAULT 1,
            category VARCHAR(30) DEFAULT 'unknown',
            ai_analyzed BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_web_audit_entries_tenant_date ON web_audit_entries(tenant_id, visited_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_web_audit_entries_tenant_user ON web_audit_entries(tenant_id, ad_user)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_web_audit_entries_tenant_domain ON web_audit_entries(tenant_id, domain)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS web_audit_findings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            entry_id UUID REFERENCES web_audit_entries(id) ON DELETE SET NULL,
            workstation VARCHAR(255) NOT NULL,
            ad_user VARCHAR(255),
            department VARCHAR(255),
            finding_type VARCHAR(50) NOT NULL,
            severity VARCHAR(20) NOT NULL DEFAULT 'medium',
            domain TEXT NOT NULL,
            description TEXT NOT NULL,
            recommendation TEXT,
            ai_confidence FLOAT,
            soar_triggered BOOLEAN NOT NULL DEFAULT FALSE,
            soar_execution_id UUID,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_web_audit_findings_tenant_date ON web_audit_findings(tenant_id, created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_web_audit_findings_tenant_severity ON web_audit_findings(tenant_id, severity)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS web_audit_findings")
    op.execute("DROP TABLE IF EXISTS web_audit_entries")
    op.execute("DROP TABLE IF EXISTS web_audit_configs")
