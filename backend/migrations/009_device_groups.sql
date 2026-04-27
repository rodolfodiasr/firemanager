-- Phase 10: Device Groups
CREATE TABLE IF NOT EXISTS device_groups (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id   UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    created_by  UUID NOT NULL REFERENCES users(id),
    name        VARCHAR(100) NOT NULL,
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_device_groups_tenant ON device_groups(tenant_id);

CREATE TABLE IF NOT EXISTS device_group_members (
    group_id   UUID NOT NULL REFERENCES device_groups(id) ON DELETE CASCADE,
    device_id  UUID NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    added_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (group_id, device_id)
);

CREATE INDEX IF NOT EXISTS idx_dgm_group  ON device_group_members(group_id);
CREATE INDEX IF NOT EXISTS idx_dgm_device ON device_group_members(device_id);
