CREATE TABLE IF NOT EXISTS v2.scenario_run_batches (
    batch_run_id   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id       UUID NOT NULL REFERENCES v2.agent(agent_id) ON DELETE CASCADE,
    user_id        UUID NOT NULL REFERENCES v2.user(user_id) ON DELETE CASCADE,
    scenario_ids   JSONB NOT NULL DEFAULT '[]'::jsonb,
    status         TEXT NOT NULL DEFAULT 'PENDING',
    statistics     JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    completed_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_scenario_run_batches_agent_id_created_at
  ON v2.scenario_run_batches (agent_id, created_at DESC);

ALTER TABLE v2.scenario_runs
    ADD COLUMN IF NOT EXISTS batch_run_id UUID REFERENCES v2.scenario_run_batches(batch_run_id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_scenario_runs_batch_run_id
  ON v2.scenario_runs (batch_run_id);
