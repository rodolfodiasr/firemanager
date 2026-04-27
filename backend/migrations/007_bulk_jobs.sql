-- Migration 007: Bulk jobs (operações em lote em múltiplos devices)
CREATE TABLE IF NOT EXISTS bulk_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    created_by      UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    description     TEXT NOT NULL,
    status          VARCHAR(50) NOT NULL DEFAULT 'pending',
    device_count    INT NOT NULL DEFAULT 0,
    completed_count INT NOT NULL DEFAULT 0,
    failed_count    INT NOT NULL DEFAULT 0,
    intent          VARCHAR(100),
    error_summary   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_bulk_jobs_tenant   ON bulk_jobs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_bulk_jobs_status   ON bulk_jobs(status);

-- Vincular operações existentes a bulk jobs
ALTER TABLE operations
    ADD COLUMN IF NOT EXISTS bulk_job_id UUID REFERENCES bulk_jobs(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_operations_bulk_job ON operations(bulk_job_id);
