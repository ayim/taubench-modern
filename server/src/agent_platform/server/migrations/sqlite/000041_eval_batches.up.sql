CREATE TABLE IF NOT EXISTS v2_scenario_run_batches (
    batch_run_id   TEXT PRIMARY KEY,
    agent_id       TEXT NOT NULL REFERENCES v2_agent(agent_id) ON DELETE CASCADE,
    user_id        TEXT NOT NULL REFERENCES v2_user(user_id) ON DELETE CASCADE,
    scenario_ids   JSON NOT NULL DEFAULT '[]',
    status         TEXT NOT NULL DEFAULT 'PENDING',
    statistics     JSON NOT NULL DEFAULT '{}',
    created_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at     TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    completed_at   TEXT
);

CREATE INDEX IF NOT EXISTS idx_scenario_run_batches_agent_id_created_at
  ON v2_scenario_run_batches (agent_id, created_at);

ALTER TABLE v2_scenario_runs
    ADD COLUMN batch_run_id TEXT REFERENCES v2_scenario_run_batches(batch_run_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_scenario_runs_batch_run_id
  ON v2_scenario_runs (batch_run_id);
