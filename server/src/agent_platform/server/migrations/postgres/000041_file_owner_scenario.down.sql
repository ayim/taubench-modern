ALTER TABLE v2."file_owner"
    DROP CONSTRAINT IF EXISTS unique_file_ref_scenario_v2;

DROP INDEX IF EXISTS idx_file_owner_scenario_id_v2;

ALTER TABLE v2."file_owner"
    DROP CONSTRAINT IF EXISTS fk_file_owner_scenario_id_v2;

ALTER TABLE v2."file_owner"
    DROP COLUMN IF EXISTS scenario_id;
