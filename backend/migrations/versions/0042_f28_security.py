"""Fase 28 — Segurança Avançada: read_only_agent flag, hash-chained audit_logs index.

Revision ID: 0042
Revises: 0041
Create Date: 2026-05-10
"""
from alembic import op
from sqlalchemy import text

revision = "0042"
down_revision = "0041"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # read_only_agent: prevents ALL write operations via AI agent on this device
    op.execute(text("""
        ALTER TABLE devices
        ADD COLUMN IF NOT EXISTS read_only_agent BOOLEAN NOT NULL DEFAULT FALSE
    """))

    # Ensure audit_logs has indexes for hash-chain verification queries
    op.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_audit_logs_created_at
        ON audit_logs(created_at DESC)
    """))
    op.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_audit_logs_user_action
        ON audit_logs(user_id, action)
    """))


def downgrade() -> None:
    op.execute(text("ALTER TABLE devices DROP COLUMN IF EXISTS read_only_agent"))
    op.execute(text("DROP INDEX IF EXISTS ix_audit_logs_created_at"))
    op.execute(text("DROP INDEX IF EXISTS ix_audit_logs_user_action"))
