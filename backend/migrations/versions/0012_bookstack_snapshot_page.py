"""BookStack periodic snapshot page ID on devices

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-01

Changes:
  - devices: add bookstack_snapshot_page_id (int, nullable)
    Stores the ID of the FM periodic snapshot page in BookStack.
    This page is overwritten on each snapshot run (not append-only).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("bookstack_snapshot_page_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("devices", "bookstack_snapshot_page_id")
