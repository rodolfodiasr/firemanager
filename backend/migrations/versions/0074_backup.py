"""backup module — backup_configs + backup_jobs

Revision ID: 0074
Revises: 0073
Create Date: 2026-05-14
"""
from alembic import op

revision = "0074"
down_revision = "0073"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS backup_configs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            backup_type VARCHAR(20) NOT NULL DEFAULT 'platform',
            destination VARCHAR(20) NOT NULL DEFAULT 'local',
            schedule_cron VARCHAR(50),
            retention_count INTEGER NOT NULL DEFAULT 7,
            local_path VARCHAR(500),
            s3_bucket VARCHAR(255),
            s3_prefix VARCHAR(255),
            s3_region VARCHAR(50),
            s3_credentials_encrypted TEXT,
            sftp_host VARCHAR(255),
            sftp_port INTEGER DEFAULT 22,
            sftp_user VARCHAR(100),
            sftp_credentials_encrypted TEXT,
            sftp_path VARCHAR(500),
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_backup_configs_tenant_id ON backup_configs(tenant_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS backup_jobs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            config_id UUID NOT NULL REFERENCES backup_configs(id) ON DELETE CASCADE,
            tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
            triggered_by UUID REFERENCES users(id) ON DELETE SET NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            backup_type VARCHAR(20) NOT NULL DEFAULT 'platform',
            destination VARCHAR(20) NOT NULL DEFAULT 'local',
            file_path VARCHAR(500),
            file_size_bytes BIGINT,
            error_message TEXT,
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_backup_jobs_config_id ON backup_jobs(config_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_backup_jobs_tenant_id ON backup_jobs(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_backup_jobs_created_at ON backup_jobs(created_at)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS backup_jobs")
    op.execute("DROP TABLE IF EXISTS backup_configs")
