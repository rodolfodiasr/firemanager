"""F35.cont — SOAR Builder Visual: builder_state em playbook_rules."""
from alembic import op

revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE playbook_rules ADD COLUMN IF NOT EXISTS builder_state JSONB")


def downgrade() -> None:
    op.execute("ALTER TABLE playbook_rules DROP COLUMN IF EXISTS builder_state")
