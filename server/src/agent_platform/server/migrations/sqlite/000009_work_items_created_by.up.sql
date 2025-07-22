-- Add created_by column with NOT NULL and sentinel default
ALTER TABLE v2_work_items ADD COLUMN created_by TEXT NOT NULL DEFAULT 'PLACEHOLDER';

-- Update created_by to equal user_id for all records
UPDATE v2_work_items SET created_by = user_id; 