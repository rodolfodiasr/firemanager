"""investigation: add device_ids JSONB for multi-device sessions

Revision ID: 0078
Revises: 0077
"""
from alembic import op


def upgrade() -> None:
    op.execute("""
        ALTER TABLE investigation_sessions
        ADD COLUMN IF NOT EXISTS device_ids JSONB DEFAULT '[]'
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE investigation_sessions DROP COLUMN IF EXISTS device_ids")
