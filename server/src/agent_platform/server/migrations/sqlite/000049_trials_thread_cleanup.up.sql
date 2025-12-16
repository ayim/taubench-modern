ALTER TABLE v2_thread
    ADD COLUMN trial_id TEXT REFERENCES v2_trials(trial_id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_thread_trial_id_v2 ON v2_thread(trial_id);
