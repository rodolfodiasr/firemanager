-- Migration 003: Multi-tenant foundation
-- Run inside a transaction. The DEFAULT tenant is created here so existing
-- devices and users are preserved without data loss.

BEGIN;

-- ── 1. Tenants ────────────────────────────────────────────────────────────────

CREATE TABLE tenants (
    id         UUID        NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
    name       VARCHAR(100) NOT NULL,
    slug       VARCHAR(100) NOT NULL UNIQUE,
    is_active  BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_tenants_slug ON tenants (slug);

-- Default tenant for all pre-existing data
INSERT INTO tenants (name, slug)
VALUES ('Default', 'default');

-- ── 2. User: is_super_admin ──────────────────────────────────────────────────

ALTER TABLE users
    ADD COLUMN is_super_admin BOOLEAN NOT NULL DEFAULT FALSE;

-- ── 3. Devices: tenant_id ────────────────────────────────────────────────────

ALTER TABLE devices
    ADD COLUMN tenant_id UUID REFERENCES tenants(id) ON DELETE RESTRICT;

-- Assign all existing devices to the default tenant
UPDATE devices
SET tenant_id = (SELECT id FROM tenants WHERE slug = 'default');

ALTER TABLE devices
    ALTER COLUMN tenant_id SET NOT NULL;

CREATE INDEX ix_devices_tenant_id ON devices (tenant_id);

-- ── 4. User-tenant roles ─────────────────────────────────────────────────────

CREATE TABLE user_tenant_roles (
    user_id    UUID        NOT NULL REFERENCES users(id)   ON DELETE CASCADE,
    tenant_id  UUID        NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    role       VARCHAR(20) NOT NULL DEFAULT 'analyst',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, tenant_id)
);

CREATE INDEX ix_user_tenant_roles_tenant_id ON user_tenant_roles (tenant_id);

-- Assign all existing users to the default tenant
-- Existing admins become tenant admins; everyone else becomes analyst
INSERT INTO user_tenant_roles (user_id, tenant_id, role)
SELECT
    u.id,
    (SELECT id FROM tenants WHERE slug = 'default'),
    CASE WHEN u.role = 'admin' THEN 'admin' ELSE 'analyst' END
FROM users u;

COMMIT;
