"""invite_tokens: add auth_source column for mixed auth support

Revision ID: 0080
Revises: 0079
"""
from alembic import op

revision = "0080"
down_revision = "0079"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE invite_tokens
        ADD COLUMN IF NOT EXISTS auth_source VARCHAR(20) NOT NULL DEFAULT 'local'
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE invite_tokens DROP COLUMN IF EXISTS auth_source")
