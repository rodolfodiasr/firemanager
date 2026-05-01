"""BookStack documentation draft page ID on devices

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-01

Changes:
  - devices: add bookstack_doc_page_id (int, nullable)
    Stores the ID of the FM-generated documentation draft page in BookStack.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("bookstack_doc_page_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("devices", "bookstack_doc_page_id")
