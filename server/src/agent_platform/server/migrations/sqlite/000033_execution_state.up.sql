ALTER TABLE v2_trials ADD COLUMN execution_state JSON NOT NULL DEFAULT '{}';
ALTER TABLE v2_trials DROP COLUMN messages;