BEGIN;

CREATE TABLE IF NOT EXISTS integrations (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID        REFERENCES tenants(id) ON DELETE CASCADE,  -- NULL = global
    type        VARCHAR(50) NOT NULL,
    name        VARCHAR(100) NOT NULL,
    encrypted_config TEXT   NOT NULL DEFAULT '{}',
    is_active   BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_integrations_tenant_id ON integrations(tenant_id);
CREATE INDEX IF NOT EXISTS ix_integrations_type ON integrations(type);
-- Unique: one config per (type, tenant). NULL tenant = global.
CREATE UNIQUE INDEX IF NOT EXISTS uq_integrations_type_tenant
    ON integrations(type, COALESCE(tenant_id::text, 'global'));

COMMIT;
