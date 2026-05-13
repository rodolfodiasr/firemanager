"""F35.cont — SOAR Builder Visual: builder_state em playbook_rules."""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0060"
down_revision = "0059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "playbook_rules",
        sa.Column("builder_state", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("playbook_rules", "builder_state")
