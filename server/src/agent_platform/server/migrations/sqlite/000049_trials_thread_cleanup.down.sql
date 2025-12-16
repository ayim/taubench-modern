DROP INDEX IF EXISTS idx_thread_trial_id_v2;

ALTER TABLE v2_thread
    DROP COLUMN IF EXISTS trial_id;
