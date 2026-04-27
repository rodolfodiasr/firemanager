-- ============================================================
-- FireManager — Rule Templates Migration
-- Run on the server:
--   docker compose -f infra/docker-compose.yml exec postgres \
--     psql -U fm_user -d firemanager -f /tmp/migration_templates.sql
-- ============================================================

CREATE TABLE IF NOT EXISTS rule_templates (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug        VARCHAR(120) UNIQUE NOT NULL,
    name        VARCHAR(200) NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    category    VARCHAR(100) NOT NULL,
    vendor      VARCHAR(50)  NOT NULL,
    firmware_pattern VARCHAR(50) NOT NULL DEFAULT '*',
    parameters  JSONB NOT NULL DEFAULT '[]',
    ssh_commands JSONB NOT NULL DEFAULT '[]',
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_by_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
