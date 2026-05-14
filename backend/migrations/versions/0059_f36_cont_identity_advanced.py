"""F36.cont — Governança de Identidade: postura, role mining, saúde de grupos."""
from alembic import op

revision = "0059"
down_revision = "0058"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS identity_posture_snapshots (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            score INTEGER NOT NULL,
            mfa_pct FLOAT,
            admin_permanent_pct FLOAT,
            campaigns_on_time_pct FLOAT,
            sod_critical_open INTEGER,
            inactive_accounts INTEGER,
            details JSONB,
            computed_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_identity_posture_tenant_id ON identity_posture_snapshots(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_identity_posture_computed_at ON identity_posture_snapshots(tenant_id, computed_at)")

    # user_id sem FK para ad_users — tabela pode não existir neste deployment
    op.execute("""
        CREATE TABLE IF NOT EXISTS excessive_access_alerts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            user_id UUID NOT NULL,
            rule_type VARCHAR(60) NOT NULL,
            details JSONB,
            severity VARCHAR(20) NOT NULL DEFAULT 'medium',
            status VARCHAR(20) NOT NULL DEFAULT 'open',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_excessive_access_tenant_id ON excessive_access_alerts(tenant_id)")

    # group_id sem FK para ad_groups — tabela pode não existir neste deployment
    op.execute("""
        CREATE TABLE IF NOT EXISTS group_health_reports (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            group_id UUID NOT NULL,
            health_score INTEGER NOT NULL,
            issues JSONB,
            analyzed_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_group_health_tenant_id ON group_health_reports(tenant_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS role_profiles (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            job_title VARCHAR(200) NOT NULL,
            department VARCHAR(200),
            standard_groups JSONB,
            computed_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_role_profiles_tenant_id ON role_profiles(tenant_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS role_profiles")
    op.execute("DROP TABLE IF EXISTS group_health_reports")
    op.execute("DROP TABLE IF EXISTS excessive_access_alerts")
    op.execute("DROP TABLE IF EXISTS identity_posture_snapshots")
