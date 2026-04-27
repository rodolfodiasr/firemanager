-- Migration 006: Device category (firewall / router / switch / l3_switch)
ALTER TABLE devices
    ADD COLUMN IF NOT EXISTS category VARCHAR(50) NOT NULL DEFAULT 'firewall';

-- Existing devices are all firewalls — default is correct.
-- New vendors for routers/switches stored as plain VARCHAR (native_enum=False).
