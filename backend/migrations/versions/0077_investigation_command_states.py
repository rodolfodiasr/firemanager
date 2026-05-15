"""investigation_command_states: per-command approval/edit/reject states in investigation phases.

Revision ID: 0077
Revises: 0076
"""
from alembic import op

revision = "0077"
down_revision = "0076"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE investigation_phases
        ADD COLUMN IF NOT EXISTS command_states JSONB DEFAULT '[]'
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE investigation_phases DROP COLUMN IF EXISTS command_states")
