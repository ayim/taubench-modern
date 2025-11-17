ALTER TABLE v2.trials
    ADD COLUMN IF NOT EXISTS retry_after_at TIMESTAMPTZ NULL;

CREATE INDEX IF NOT EXISTS idx_trials_retry_after_at
    ON v2.trials (retry_after_at)
    WHERE status = 'PENDING';

ALTER TABLE v2.trials
    ADD COLUMN IF NOT EXISTS reschedule_attempts INTEGER NOT NULL DEFAULT 0;
