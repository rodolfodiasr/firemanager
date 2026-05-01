"""BookStack integration — device and device_group fields

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-01

Changes:
  - devices: add bookstack_page_id (int, nullable)
  - devices: add bookstack_fm_page_id (int, nullable)
  - device_groups: add bookstack_chapter_id (int, nullable)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("bookstack_page_id", sa.Integer(), nullable=True))
    op.add_column("devices", sa.Column("bookstack_fm_page_id", sa.Integer(), nullable=True))
    op.add_column("device_groups", sa.Column("bookstack_chapter_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("device_groups", "bookstack_chapter_id")
    op.drop_column("devices", "bookstack_fm_page_id")
    op.drop_column("devices", "bookstack_page_id")
