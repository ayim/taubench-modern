CREATE TABLE IF NOT EXISTS v2.scenarios (
    scenario_id       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name              TEXT NOT NULL,
    description       TEXT NOT NULL,
    thread_id         UUID REFERENCES v2.thread(thread_id) ON DELETE SET NULL,
    agent_id          UUID NOT NULL REFERENCES v2.agent(agent_id) ON DELETE CASCADE,
    user_id           UUID NOT NULL REFERENCES v2.user(user_id) ON DELETE CASCADE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    messages          JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata          JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_scenarios_agent_id ON v2.scenarios (agent_id);

CREATE TABLE IF NOT EXISTS v2.scenario_runs (
    scenario_run_id   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scenario_id       UUID NOT NULL REFERENCES v2.scenarios(scenario_id) ON DELETE CASCADE,
    user_id           UUID NOT NULL REFERENCES v2.user(user_id) ON DELETE CASCADE,
    num_trials        INT NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    configuration     JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_scenario_runs_scenario_id_created_at
  ON v2.scenario_runs (scenario_id, created_at DESC);

CREATE TABLE IF NOT EXISTS v2.trials (
    trial_id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scenario_run_id   UUID REFERENCES v2.scenario_runs(scenario_run_id) ON DELETE CASCADE,
    scenario_id       UUID REFERENCES v2.scenarios(scenario_id) ON DELETE CASCADE,

    thread_id         UUID REFERENCES v2.thread(thread_id) ON DELETE SET NULL,

    index_in_run      INT NOT NULL,
    messages          JSONB NOT NULL DEFAULT '[]'::jsonb,

    status            TEXT NOT NULL DEFAULT 'PENDING',
    created_at        TIMESTAMPTZ NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    
    status_updated_at  TIMESTAMPTZ NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    status_updated_by  TEXT NOT NULL DEFAULT 'SYSTEM',

    error_message     TEXT,

    metadata          JSONB NOT NULL DEFAULT '{}'::jsonb
);


CREATE INDEX IF NOT EXISTS idx_trials_run_id_index_in_run ON v2.trials (scenario_run_id, index_in_run);
CREATE INDEX IF NOT EXISTS idx_trials_status_created      ON v2.trials(status, created_at)
                                                          WHERE status = 'PENDING';