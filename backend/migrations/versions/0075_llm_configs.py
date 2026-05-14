"""llm_configs: multi-provider LLM configuration — global (super admin) e por tenant.

Revision ID: 0075
Revises: 0074
"""
from alembic import op

revision = "0075"
down_revision = "0074"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS llm_configs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
            provider VARCHAR(50) NOT NULL,
            display_name VARCHAR(100) NOT NULL,
            api_key_encrypted TEXT,
            api_base_url VARCHAR(500),
            model_name VARCHAR(100) NOT NULL,
            is_enabled BOOLEAN NOT NULL DEFAULT true,
            is_default BOOLEAN NOT NULL DEFAULT false,
            priority INTEGER NOT NULL DEFAULT 0,
            no_train_flag BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_llm_configs_tenant_id ON llm_configs(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_llm_configs_provider ON llm_configs(provider)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS llm_configs")
