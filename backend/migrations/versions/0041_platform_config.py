"""Fase 28 — Platform config table (API keys in DB).

Revision ID: 0041
Revises: 0040
Create Date: 2026-05-08
"""
from alembic import op
from sqlalchemy import text

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(text("""
        CREATE TABLE platform_config (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            key VARCHAR(100) NOT NULL UNIQUE,
            encrypted_value TEXT,
            description VARCHAR(500),
            is_sensitive BOOLEAN NOT NULL DEFAULT TRUE,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    op.execute(text("CREATE INDEX ix_platform_config_key ON platform_config(key)"))


def downgrade() -> None:
    op.execute(text("DROP TABLE IF EXISTS platform_config"))
