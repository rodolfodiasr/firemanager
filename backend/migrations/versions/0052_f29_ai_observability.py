"""F29: ai_interactions, ai_token_usage, confidence_score em operations.

Revision ID: 0052
Revises: 0051
Create Date: 2026-05-12
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # ai_interactions — rastreio de cada chamada LLM (prompt + resposta)
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS ai_interactions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            operation_id UUID REFERENCES operations(id) ON DELETE SET NULL,
            session_id UUID REFERENCES assistant_sessions(id) ON DELETE SET NULL,
            model VARCHAR(100) NOT NULL,
            prompt_tokens INTEGER NOT NULL DEFAULT 0,
            completion_tokens INTEGER NOT NULL DEFAULT 0,
            total_tokens INTEGER NOT NULL DEFAULT 0,
            prompt_hash VARCHAR(64),
            injection_score FLOAT DEFAULT 0,
            duration_ms INTEGER,
            sub_agent VARCHAR(50),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_ai_interactions_tenant ON ai_interactions(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ai_interactions_op ON ai_interactions(operation_id) WHERE operation_id IS NOT NULL")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ai_interactions_month ON ai_interactions(tenant_id, created_at)")

    # ------------------------------------------------------------------
    # ai_token_usage — agregação mensal por tenant (billing / quotas)
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS ai_token_usage (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            month VARCHAR(7) NOT NULL,
            input_tokens BIGINT NOT NULL DEFAULT 0,
            output_tokens BIGINT NOT NULL DEFAULT 0,
            total_tokens BIGINT NOT NULL DEFAULT 0,
            cost_usd FLOAT DEFAULT 0,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, month)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_ai_token_usage_tenant ON ai_token_usage(tenant_id)")

    # ------------------------------------------------------------------
    # confidence_score em operations — threshold para auto-escalação
    # ------------------------------------------------------------------
    op.execute("""
        ALTER TABLE operations
        ADD COLUMN IF NOT EXISTS confidence_score FLOAT
    """)

    # ------------------------------------------------------------------
    # orchestration_run — registra execuções do orquestrador multi-agente
    # ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE IF NOT EXISTS orchestration_runs (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            operation_id UUID REFERENCES operations(id) ON DELETE SET NULL,
            user_query TEXT NOT NULL,
            agents_invoked JSONB NOT NULL DEFAULT '[]',
            result JSONB,
            status VARCHAR(30) NOT NULL DEFAULT 'running',
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            finished_at TIMESTAMPTZ
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_orch_runs_tenant ON orchestration_runs(tenant_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS orchestration_runs")
    op.execute("ALTER TABLE operations DROP COLUMN IF EXISTS confidence_score")
    op.execute("DROP TABLE IF EXISTS ai_token_usage")
    op.execute("DROP TABLE IF EXISTS ai_interactions")
