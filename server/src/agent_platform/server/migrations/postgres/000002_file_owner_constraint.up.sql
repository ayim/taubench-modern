-- drop the unique constraint on file_ref, agent_id
ALTER TABLE v2."file_owner" DROP CONSTRAINT IF EXISTS unique_file_ref_agent_v2;
