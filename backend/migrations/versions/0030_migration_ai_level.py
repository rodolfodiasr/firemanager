"""config_migrations: add ai_level column

Revision ID: 0030
Revises: 0029
Create Date: 2026-05-07
"""
from alembic import op
import sqlalchemy as sa

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "config_migrations",
        sa.Column("ai_level", sa.Integer(), nullable=False, server_default="2"),
    )


def downgrade() -> None:
    op.drop_column("config_migrations", "ai_level")
