"""0090 — Servers: campo use_sudo para escalação de privilégio no SSH."""
from alembic import op
import sqlalchemy as sa

revision = "0090"
down_revision = "0089"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "servers",
        sa.Column("use_sudo", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_column("servers", "use_sudo")
