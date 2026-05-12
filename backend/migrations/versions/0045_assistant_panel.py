"""Fase 40-B: AI Assistant Panel — tabelas assistant_sessions e assistant_messages.

Revision ID: 0045
Revises: 0044
Create Date: 2026-05-12
"""
from alembic import op

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS assistant_sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            title TEXT,
            model_used VARCHAR(100) NOT NULL DEFAULT 'claude-sonnet-4-6',
            message_count INTEGER NOT NULL DEFAULT 0,
            last_hash VARCHAR(64),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_assistant_sessions_tenant_user "
        "ON assistant_sessions(tenant_id, user_id)"
    )

    op.execute("""
        CREATE TABLE IF NOT EXISTS assistant_messages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id UUID NOT NULL REFERENCES assistant_sessions(id) ON DELETE CASCADE,
            role VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            model VARCHAR(100),
            input_tokens INTEGER,
            output_tokens INTEGER,
            rag_context_used BOOLEAN NOT NULL DEFAULT FALSE,
            message_hash VARCHAR(64) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_assistant_messages_session "
        "ON assistant_messages(session_id, created_at)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS assistant_messages")
    op.execute("DROP TABLE IF EXISTS assistant_sessions")
