"""Fase 25 — Enterprise Platform: tenant_branding and api_keys tables.

Revision ID: 0038
Revises: 0037
Create Date: 2026-05-08
"""
from alembic import op
from sqlalchemy import text

revision = "0038"
down_revision = "0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # vendors column is VARCHAR (native_enum=False in SQLAlchemy model)
    # so no ALTER TYPE needed — new enum values work automatically.

    op.execute(text("""
        CREATE TABLE tenant_branding (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL UNIQUE REFERENCES tenants(id) ON DELETE CASCADE,
            company_name VARCHAR(200),
            primary_color VARCHAR(7),
            logo_url VARCHAR(500),
            favicon_url VARCHAR(500),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))

    op.execute(text("""
        CREATE INDEX ix_tenant_branding_tenant_id ON tenant_branding(tenant_id)
    """))

    op.execute(text("""
        CREATE TABLE api_keys (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            key_prefix VARCHAR(8) NOT NULL,
            key_hash VARCHAR(256) NOT NULL,
            permissions JSONB NOT NULL DEFAULT '[]',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            last_used_at TIMESTAMPTZ,
            expires_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))

    op.execute(text("""
        CREATE INDEX ix_api_keys_tenant_id ON api_keys(tenant_id)
    """))

    op.execute(text("""
        CREATE INDEX ix_api_keys_key_prefix ON api_keys(key_prefix)
    """))


def downgrade() -> None:
    op.execute(text("DROP TABLE IF EXISTS api_keys"))
    op.execute(text("DROP TABLE IF EXISTS tenant_branding"))
