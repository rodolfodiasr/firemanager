"""F35: SOAR — playbook_rules, playbook_executions, threat_indicators.

Revision ID: 0055
Revises: 0054
Create Date: 2026-05-13
"""
from alembic import op

revision = "0055"
down_revision = "0054"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # playbook_rules — regras de automação SOAR
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS playbook_rules (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(200) NOT NULL,
            description TEXT,
            trigger_type VARCHAR(50) NOT NULL,
            trigger_condition JSONB NOT NULL DEFAULT '{}',
            actions JSONB NOT NULL DEFAULT '[]',
            cooldown_minutes INTEGER NOT NULL DEFAULT 30,
            enabled BOOLEAN NOT NULL DEFAULT true,
            is_template BOOLEAN NOT NULL DEFAULT false,
            template_name VARCHAR(100),
            created_by UUID REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_pb_rules_tenant ON playbook_rules(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_pb_rules_trigger ON playbook_rules(tenant_id, trigger_type)")

    # ------------------------------------------------------------------
    # playbook_executions — histórico de execuções e MTTR
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS playbook_executions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            rule_id UUID NOT NULL REFERENCES playbook_rules(id) ON DELETE CASCADE,
            triggered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            trigger_context JSONB NOT NULL DEFAULT '{}',
            actions_taken JSONB NOT NULL DEFAULT '[]',
            status VARCHAR(20) NOT NULL DEFAULT 'running',
            resolved_at TIMESTAMPTZ,
            error_message TEXT
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_pb_exec_tenant ON playbook_executions(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_pb_exec_rule ON playbook_executions(rule_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_pb_exec_status ON playbook_executions(tenant_id, status)")

    # ------------------------------------------------------------------
    # threat_indicators — IoCs de feeds externos (OTX, AbuseIPDB, CISA)
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS threat_indicators (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            ioc_type VARCHAR(20) NOT NULL,
            value VARCHAR(500) NOT NULL,
            source VARCHAR(50) NOT NULL,
            severity VARCHAR(20) NOT NULL DEFAULT 'medium',
            tags JSONB NOT NULL DEFAULT '[]',
            confidence FLOAT DEFAULT 0.8,
            last_seen TIMESTAMPTZ NOT NULL DEFAULT now(),
            expires_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (ioc_type, value, source)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_ioc_type_val ON threat_indicators(ioc_type, value)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ioc_severity ON threat_indicators(severity)")


def downgrade() -> None:
    for tbl in ["threat_indicators", "playbook_executions", "playbook_rules"]:
        op.execute(f"DROP TABLE IF EXISTS {tbl}")
