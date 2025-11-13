DROP INDEX IF EXISTS idx_scenario_runs_batch_run_id;
ALTER TABLE v2.scenario_runs DROP COLUMN IF EXISTS batch_run_id;
DROP INDEX IF EXISTS idx_scenario_run_batches_agent_id_created_at;
DROP TABLE IF EXISTS v2.scenario_run_batches;
