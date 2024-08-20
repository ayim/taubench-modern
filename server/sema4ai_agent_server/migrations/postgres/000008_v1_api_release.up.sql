ALTER TABLE assistant RENAME TO agent;
ALTER TABLE agent RENAME COLUMN assistant_id TO id;
ALTER TABLE thread RENAME COLUMN assistant_id TO agent_id;
ALTER TABLE file_owners RENAME COLUMN assistant_id TO agent_id;
