-- Phase 8: SSH/CLI connectors — add new vendor values
-- The vendor column is VARCHAR (native_enum=False), so new values are just allowed.
-- This migration documents the change; no schema alteration is required.

-- Add 'dell' as a valid vendor value in any CHECK constraints (none currently exist).
-- If you added a CHECK constraint manually, run:
--   ALTER TABLE devices DROP CONSTRAINT IF EXISTS devices_vendor_check;

-- Verify existing devices are unaffected:
SELECT vendor, COUNT(*) FROM devices GROUP BY vendor ORDER BY vendor;
