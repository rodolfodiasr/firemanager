-- FireManager — Edit Operations Migration
-- Adds parent_operation_id for tracking edit lineage

ALTER TABLE operations
  ADD COLUMN IF NOT EXISTS parent_operation_id UUID REFERENCES operations(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_operations_parent ON operations(parent_operation_id)
  WHERE parent_operation_id IS NOT NULL;
