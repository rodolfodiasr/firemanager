"""F29.cont — Add plan tier to api_keys for rate limiting.

Also ensures api_keys and tenant_branding tables exist (0038 may have been
stamped without running on some deployments).
"""
from alembic import op

revision = "0056"
down_revision = "0055"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure tenant_branding exists (created in 0038; may have been stamped)
    op.execute("""
        CREATE TABLE IF NOT EXISTS tenant_branding (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL UNIQUE REFERENCES tenants(id) ON DELETE CASCADE,
            company_name VARCHAR(200),
            primary_color VARCHAR(7),
            logo_url VARCHAR(500),
            favicon_url VARCHAR(500),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_tenant_branding_tenant_id ON tenant_branding(tenant_id)")

    # Ensure api_keys exists with all columns including plan
    op.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            name VARCHAR(100) NOT NULL,
            key_prefix VARCHAR(8) NOT NULL,
            key_hash VARCHAR(256) NOT NULL,
            permissions JSONB NOT NULL DEFAULT '[]',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            last_used_at TIMESTAMPTZ,
            expires_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            plan VARCHAR(20) NOT NULL DEFAULT 'starter'
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS ix_api_keys_tenant_id ON api_keys(tenant_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_api_keys_key_prefix ON api_keys(key_prefix)")

    # Add plan column if table already existed without it
    op.execute("ALTER TABLE api_keys ADD COLUMN IF NOT EXISTS plan VARCHAR(20) NOT NULL DEFAULT 'starter'")


def downgrade() -> None:
    op.execute("ALTER TABLE api_keys DROP COLUMN IF EXISTS plan")
