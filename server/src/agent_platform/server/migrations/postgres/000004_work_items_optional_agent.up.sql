-- Add work_item_id column to file_owner table and make agent_id optional in work_items

-- Add work_item_id column to file_owner table
ALTER TABLE v2."file_owner" ADD COLUMN work_item_id UUID;

-- Add foreign key constraint to work_items table
ALTER TABLE v2."file_owner" ADD CONSTRAINT fk_file_owner_work_item_id_v2
    FOREIGN KEY (work_item_id)
    REFERENCES v2.work_items(work_item_id)
    ON DELETE CASCADE;

-- Create index for work_item_id lookups
CREATE INDEX idx_file_owner_work_item_id_v2 
    ON v2."file_owner"(work_item_id);

-- Make agent_id optional in work_items table
ALTER TABLE v2.work_items ALTER COLUMN agent_id DROP NOT NULL; 