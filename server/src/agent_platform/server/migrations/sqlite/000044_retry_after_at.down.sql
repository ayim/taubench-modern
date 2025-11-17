DROP INDEX IF EXISTS idx_trials_retry_after_at;

ALTER TABLE v2_trials
    DROP COLUMN IF EXISTS retry_after_at;

ALTER TABLE v2_trials
    DROP COLUMN IF EXISTS reschedule_attempts;
