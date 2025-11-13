DROP INDEX IF EXISTS idx_scenario_runs_batch_run_id;
ALTER TABLE v2_scenario_runs DROP COLUMN batch_run_id;
DROP INDEX IF EXISTS idx_scenario_run_batches_agent_id_created_at;
DROP TABLE IF EXISTS v2_scenario_run_batches;
