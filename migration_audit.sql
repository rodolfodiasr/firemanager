-- ============================================================
-- FireManager — Audit Module Migration
-- Run inside the db container:
--   docker compose -f infra/docker-compose.yml exec db \
--     psql -U postgres -d firemanager -f /tmp/migration_audit.sql
-- ============================================================

-- 1. Add audit review fields to the operations table
ALTER TABLE operations
    ADD COLUMN IF NOT EXISTS review_comment    TEXT,
    ADD COLUMN IF NOT EXISTS reviewer_id       UUID REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS reviewed_at       TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS executed_direct   BOOLEAN NOT NULL DEFAULT FALSE;

-- 2. Create the audit_policy table
CREATE TABLE IF NOT EXISTS audit_policy (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scope_type        VARCHAR(20)  NOT NULL CHECK (scope_type IN ('role', 'user')),
    scope_id          VARCHAR(255) NOT NULL,
    intent            VARCHAR(100) NOT NULL,
    requires_approval BOOLEAN      NOT NULL DEFAULT TRUE,
    updated_by        UUID REFERENCES users(id) ON DELETE SET NULL,
    updated_at        TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT uq_audit_policy UNIQUE (scope_type, scope_id, intent)
);

-- 3. No changes needed to the status enum — it is stored as VARCHAR (native_enum=False)
--    The Python code already handles the new 'pending_review' value.

-- Verify
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'operations'
  AND column_name IN ('review_comment', 'reviewer_id', 'reviewed_at', 'executed_direct');

SELECT 'audit_policy table: ' || COUNT(*)::text || ' rows' FROM audit_policy;
