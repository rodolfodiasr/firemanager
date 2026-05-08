"""Add is_active flag to knowledge_documents

Revision ID: 0032
Revises: 0031
Create Date: 2026-05-08
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0032"
down_revision: Union[str, None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(text(
        "ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE"
    ))


def downgrade() -> None:
    op.execute(text(
        "ALTER TABLE knowledge_documents DROP COLUMN IF EXISTS is_active"
    ))
