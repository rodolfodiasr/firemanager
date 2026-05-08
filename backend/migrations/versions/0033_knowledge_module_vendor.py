"""Add module and vendor classification to knowledge_documents

Revision ID: 0033
Revises: 0032
Create Date: 2026-05-08
"""
from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0033"
down_revision: Union[str, None] = "0032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(text(
        "ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS module VARCHAR(50)"
    ))
    op.execute(text(
        "ALTER TABLE knowledge_documents ADD COLUMN IF NOT EXISTS vendor VARCHAR(50)"
    ))
    op.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_documents_module ON knowledge_documents (module)"
    ))
    op.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_documents_vendor ON knowledge_documents (vendor)"
    ))


def downgrade() -> None:
    op.execute(text("DROP INDEX IF EXISTS ix_knowledge_documents_vendor"))
    op.execute(text("DROP INDEX IF EXISTS ix_knowledge_documents_module"))
    op.execute(text("ALTER TABLE knowledge_documents DROP COLUMN IF EXISTS vendor"))
    op.execute(text("ALTER TABLE knowledge_documents DROP COLUMN IF EXISTS module"))
