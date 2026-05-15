"""F28.1 — DLP: Prevenção de Perda de Dados no chat.

Tabelas:
  dlp_configs   — configuração global DLP por tenant
  dlp_rules     — regras por tenant (builtin + custom)
  dlp_incidents — log de incidentes (sem dado original)

Revision ID: 0067
Revises: 0066
"""
from alembic import op

revision = "0067"
down_revision = "0066"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS dlp_configs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL UNIQUE REFERENCES tenants(id) ON DELETE CASCADE,
            enabled BOOLEAN NOT NULL DEFAULT true,
            compliance_mode BOOLEAN NOT NULL DEFAULT false,
            incident_threshold_count INTEGER NOT NULL DEFAULT 5,
            incident_threshold_hours INTEGER NOT NULL DEFAULT 24,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS dlp_rules (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            rule_key VARCHAR(64) NOT NULL,
            rule_name VARCHAR(100) NOT NULL,
            description VARCHAR(255),
            category VARCHAR(32) NOT NULL,
            action VARCHAR(8) NOT NULL DEFAULT 'block',
            is_enabled BOOLEAN NOT NULL DEFAULT true,
            is_builtin BOOLEAN NOT NULL DEFAULT true,
            pattern TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_dlp_rules_tenant_key UNIQUE (tenant_id, rule_key)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_dlp_rules_tenant_id ON dlp_rules(tenant_id)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS dlp_incidents (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            pii_type VARCHAR(64) NOT NULL,
            action_taken VARCHAR(8) NOT NULL,
            source VARCHAR(32) NOT NULL DEFAULT 'chat',
            ip_address VARCHAR(45),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_dlp_incidents_tenant_id ON dlp_incidents(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_dlp_incidents_created_at ON dlp_incidents(created_at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS dlp_incidents")
    op.execute("DROP TABLE IF EXISTS dlp_rules")
    op.execute("DROP TABLE IF EXISTS dlp_configs")
