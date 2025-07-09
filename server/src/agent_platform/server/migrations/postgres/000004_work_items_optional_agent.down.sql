-- Reverse the changes: remove work_item_id column and make agent_id required again

-- Make agent_id required in work_items table
ALTER TABLE v2.work_items ALTER COLUMN agent_id SET NOT NULL;

-- Remove the index for work_item_id lookups
DROP INDEX IF EXISTS idx_file_owner_work_item_id_v2;

-- Remove foreign key constraint
ALTER TABLE v2."file_owner" DROP CONSTRAINT IF EXISTS fk_file_owner_work_item_id_v2;

-- Remove the work_item_id column
ALTER TABLE v2."file_owner" DROP COLUMN IF EXISTS work_item_id; 