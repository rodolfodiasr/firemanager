-- ============================================================
-- FireManager — Tutorial Column Migration
-- Run on the server:
--   docker compose -f infra/docker-compose.yml exec postgres \
--     psql -U fm_user -d firemanager -c \
--     "ALTER TABLE operations ADD COLUMN IF NOT EXISTS tutorial TEXT;"
-- ============================================================

ALTER TABLE operations ADD COLUMN IF NOT EXISTS tutorial TEXT;
