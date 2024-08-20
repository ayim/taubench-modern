ALTER TABLE file_owners RENAME COLUMN agent_id TO assistant_id;
ALTER TABLE thread RENAME COLUMN agent_id TO assistant_id;
ALTER TABLE agent RENAME COLUMN id TO assistant_id;
ALTER TABLE agent RENAME TO assistant;
