ALTER TABLE v2_trials DROP COLUMN execution_state;
ALTER TABLE v2_trials ADD COLUMN messages JSON NOT NULL DEFAULT '[]';