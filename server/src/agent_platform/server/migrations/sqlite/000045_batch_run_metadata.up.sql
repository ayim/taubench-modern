ALTER TABLE v2_scenario_run_batches
    ADD COLUMN metadata JSON NOT NULL DEFAULT '{}';
