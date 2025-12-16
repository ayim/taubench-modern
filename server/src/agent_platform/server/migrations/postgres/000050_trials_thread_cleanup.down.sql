DROP INDEX IF EXISTS v2.idx_thread_trial_id;

ALTER TABLE v2.thread
    DROP CONSTRAINT IF EXISTS fk_thread_trial_id;

ALTER TABLE v2.thread
    DROP COLUMN IF EXISTS trial_id;
