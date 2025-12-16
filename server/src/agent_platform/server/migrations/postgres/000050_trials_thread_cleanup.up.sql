ALTER TABLE v2.thread
    ADD COLUMN IF NOT EXISTS trial_id UUID;

ALTER TABLE v2.thread
    ADD CONSTRAINT fk_thread_trial_id
    FOREIGN KEY (trial_id)
    REFERENCES v2.trials(trial_id)
    ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_thread_trial_id ON v2.thread(trial_id);
