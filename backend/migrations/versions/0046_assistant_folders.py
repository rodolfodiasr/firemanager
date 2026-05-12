"""Fase 41: Pastas, pin e compartilhamento de sessões do AI Assistant.

Revision ID: 0046
Revises: 0045
Create Date: 2026-05-12
"""
from alembic import op

revision = "0046"
down_revision = "0045"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS assistant_folders (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            user_id UUID REFERENCES users(id) ON DELETE SET NULL,
            name TEXT NOT NULL,
            color VARCHAR(7) NOT NULL DEFAULT '#6366f1',
            is_team BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_assistant_folders_tenant "
        "ON assistant_folders(tenant_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_assistant_folders_tenant_user "
        "ON assistant_folders(tenant_id, user_id)"
    )

    op.execute(
        "ALTER TABLE assistant_sessions "
        "ADD COLUMN IF NOT EXISTS folder_id UUID "
        "REFERENCES assistant_folders(id) ON DELETE SET NULL"
    )
    op.execute(
        "ALTER TABLE assistant_sessions "
        "ADD COLUMN IF NOT EXISTS is_shared BOOLEAN NOT NULL DEFAULT FALSE"
    )
    op.execute(
        "ALTER TABLE assistant_sessions "
        "ADD COLUMN IF NOT EXISTS shared_by UUID "
        "REFERENCES users(id) ON DELETE SET NULL"
    )
    op.execute(
        "ALTER TABLE assistant_sessions "
        "ADD COLUMN IF NOT EXISTS pinned BOOLEAN NOT NULL DEFAULT FALSE"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE assistant_sessions DROP COLUMN IF EXISTS pinned")
    op.execute("ALTER TABLE assistant_sessions DROP COLUMN IF EXISTS shared_by")
    op.execute("ALTER TABLE assistant_sessions DROP COLUMN IF EXISTS is_shared")
    op.execute("ALTER TABLE assistant_sessions DROP COLUMN IF EXISTS folder_id")
    op.execute("DROP TABLE IF EXISTS assistant_folders")
