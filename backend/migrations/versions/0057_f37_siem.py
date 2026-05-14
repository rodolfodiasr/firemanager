"""F37 — SIEM connectors + normalized alerts."""
from alembic import op

revision = "0057"
down_revision = "0056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS siem_connectors (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            siem_type VARCHAR(30) NOT NULL,
            base_url TEXT NOT NULL,
            config_encrypted TEXT,
            webhook_secret VARCHAR(64) NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT true,
            last_event_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_siem_connectors_tenant_id ON siem_connectors(tenant_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS siem_alerts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            connector_id UUID NOT NULL REFERENCES siem_connectors(id) ON DELETE CASCADE,
            source_rule_id TEXT,
            severity VARCHAR(20) NOT NULL DEFAULT 'medium',
            title TEXT NOT NULL,
            description TEXT,
            affected_host TEXT,
            source_ip TEXT,
            raw_payload JSONB,
            normalized_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            playbook_triggered BOOLEAN NOT NULL DEFAULT false,
            playbook_execution_id UUID
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_siem_alerts_tenant_id ON siem_alerts(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_siem_alerts_tenant_normalized_at ON siem_alerts(tenant_id, normalized_at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS siem_alerts")
    op.execute("DROP TABLE IF EXISTS siem_connectors")
