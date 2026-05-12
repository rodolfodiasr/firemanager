"""F40-A: assistant_doc_drafts — rascunhos de documentação gerados por IA a partir de sessões.

Revision ID: 0048
Revises: 0047
Create Date: 2026-05-12
"""
from alembic import op

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS assistant_doc_drafts (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id UUID NOT NULL REFERENCES assistant_sessions(id) ON DELETE CASCADE,
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            created_by UUID REFERENCES users(id) ON DELETE SET NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'draft',
            review_deadline TIMESTAMPTZ,
            sanitizer_warnings JSONB NOT NULL DEFAULT '[]',
            bookstack_page_id INTEGER,
            bookstack_page_url TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_doc_drafts_tenant_status "
        "ON assistant_doc_drafts(tenant_id, status)"
    )

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_doc_drafts_session "
        "ON assistant_doc_drafts(session_id)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS assistant_doc_drafts")
