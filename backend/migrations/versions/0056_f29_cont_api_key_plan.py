"""F29.cont — Add plan tier to api_keys for rate limiting."""
import sqlalchemy as sa
from alembic import op

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column(
            "plan",
            sa.String(20),
            nullable=False,
            server_default="starter",
        ),
    )


def downgrade() -> None:
    op.drop_column("api_keys", "plan")
