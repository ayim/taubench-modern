-- restore the unique constraint over file_ref, agent_id
ALTER TABLE v2."file_owner_tmp" ADD CONSTRAINT unique_file_ref_agent_v2 UNIQUE (file_ref, agent_id);
