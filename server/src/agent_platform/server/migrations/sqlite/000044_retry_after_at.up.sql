ALTER TABLE v2_trials
    ADD COLUMN retry_after_at TEXT DEFAULT NULL;

CREATE INDEX IF NOT EXISTS idx_trials_retry_after_at
    ON v2_trials (retry_after_at)
    WHERE status = 'PENDING';

ALTER TABLE v2_trials
    ADD COLUMN reschedule_attempts INTEGER NOT NULL DEFAULT 0;
