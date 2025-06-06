
-- Drop the indexes so that we can recreate them later (they might exist on the old file_owner table)
drop index if exists idx_file_owner_agent_id;
drop index if exists idx_file_owner_thread_id;
drop index if exists idx_file_owner_user_id;

-- Make sure the indexes on file_owner exist (000002 should have created them and did not)
CREATE INDEX IF NOT EXISTS idx_file_owner_agent_id ON v2_file_owner(agent_id);
CREATE INDEX IF NOT EXISTS idx_file_owner_thread_id ON v2_file_owner(thread_id);
CREATE INDEX IF NOT EXISTS idx_file_owner_user_id ON v2_file_owner(user_id);