"""Fase 42: min_role em assistant_folders para controle de visibilidade por role.

Revision ID: 0047
Revises: 0046
Create Date: 2026-05-12
"""
from alembic import op

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE assistant_folders "
        "ADD COLUMN min_role VARCHAR(20) NOT NULL DEFAULT 'analyst_n1'"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE assistant_folders DROP COLUMN min_role")
