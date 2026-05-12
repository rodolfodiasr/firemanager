"""Fase 40-A: Clarification Loop — campos de clarificação e confidence score na tabela operations.

Revision ID: 0044
Revises: 0043
Create Date: 2026-05-12
"""
from alembic import op

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE operations ADD COLUMN IF NOT EXISTS clarification_questions JSONB"
    )
    op.execute(
        "ALTER TABLE operations ADD COLUMN IF NOT EXISTS clarification_answers JSONB"
    )
    op.execute(
        "ALTER TABLE operations ADD COLUMN IF NOT EXISTS confidence_score FLOAT"
    )
    # O status é armazenado como VARCHAR (native_enum=False), então basta o novo valor
    # ser usado na lógica Python — não há DDL de enum a alterar.


def downgrade() -> None:
    op.execute("ALTER TABLE operations DROP COLUMN IF EXISTS clarification_questions")
    op.execute("ALTER TABLE operations DROP COLUMN IF EXISTS clarification_answers")
    op.execute("ALTER TABLE operations DROP COLUMN IF EXISTS confidence_score")
