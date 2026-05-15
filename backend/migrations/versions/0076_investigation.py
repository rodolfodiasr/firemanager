"""investigation: investigation sessions, phases and messages for iterative diagnostics.

Revision ID: 0076
Revises: 0075
"""
from alembic import op

revision = "0076"
down_revision = "0075"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS investigation_sessions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL,
            user_id UUID NOT NULL,
            device_id UUID,
            server_id UUID,
            integration_ids JSONB,
            agent_type VARCHAR(20) NOT NULL,
            problem_description TEXT NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'planning',
            current_phase INTEGER NOT NULL DEFAULT 0,
            synthesis TEXT,
            cross_domain_detected BOOLEAN NOT NULL DEFAULT false,
            cross_domain_hint TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_investigation_sessions_tenant ON investigation_sessions(tenant_id)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS investigation_phases (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id UUID NOT NULL REFERENCES investigation_sessions(id) ON DELETE CASCADE,
            phase_number INTEGER NOT NULL,
            phase_name VARCHAR(200) NOT NULL,
            phase_purpose TEXT,
            commands JSONB NOT NULL DEFAULT '[]',
            raw_output TEXT,
            analysis TEXT,
            findings JSONB DEFAULT '[]',
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            executed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_investigation_phases_session ON investigation_phases(session_id)")
    op.execute("""
        CREATE TABLE IF NOT EXISTS investigation_messages (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id UUID NOT NULL REFERENCES investigation_sessions(id) ON DELETE CASCADE,
            role VARCHAR(20) NOT NULL,
            content TEXT NOT NULL,
            phase_number INTEGER,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_investigation_messages_session ON investigation_messages(session_id)")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS investigation_messages")
    op.execute("DROP TABLE IF EXISTS investigation_phases")
    op.execute("DROP TABLE IF EXISTS investigation_sessions")
