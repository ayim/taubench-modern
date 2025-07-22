-- Add created_by column as nullable first
ALTER TABLE v2.work_items ADD COLUMN created_by UUID;

-- Set created_by to user_id for existing records
UPDATE v2.work_items SET created_by = user_id WHERE created_by IS NULL;

-- Make created_by NOT NULL
ALTER TABLE v2.work_items ALTER COLUMN created_by SET NOT NULL; 