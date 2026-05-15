"""F37.ext — SIEM Syslog Configs: CEF forwarder universal para qualquer SIEM.

Revision ID: 0071
Revises: 0070
"""
from alembic import op

revision = "0071"
down_revision = "0070"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS siem_syslog_configs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(200) NOT NULL,
            target_host VARCHAR(300) NOT NULL,
            target_port INTEGER NOT NULL DEFAULT 514,
            protocol VARCHAR(10) NOT NULL DEFAULT 'tcp',
            tls_enabled BOOLEAN NOT NULL DEFAULT false,
            tls_verify BOOLEAN NOT NULL DEFAULT true,
            facility INTEGER NOT NULL DEFAULT 1,
            min_severity VARCHAR(20) NOT NULL DEFAULT 'low',
            event_types JSONB,
            enabled BOOLEAN NOT NULL DEFAULT true,
            last_forward_at TIMESTAMPTZ,
            events_forwarded INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_siem_syslog_configs_tenant_id ON siem_syslog_configs(tenant_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS siem_syslog_configs")
