CREATE TABLE IF NOT EXISTS v2_scenarios (
    scenario_id     TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    description     TEXT NOT NULL,
    thread_id       TEXT REFERENCES v2_thread(thread_id) ON DELETE SET NULL,
    agent_id        TEXT NOT NULL REFERENCES v2_agent(agent_id) ON DELETE CASCADE,
    user_id         TEXT NOT NULL REFERENCES v2_user(user_id) ON DELETE CASCADE,
    created_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at      TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    messages        JSON NOT NULL DEFAULT '[]',
    metadata        JSON NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_scenarios_agent_id ON v2_scenarios (agent_id);

CREATE TABLE IF NOT EXISTS v2_scenario_runs (
    scenario_run_id   TEXT PRIMARY KEY,
    scenario_id       TEXT NOT NULL REFERENCES v2_scenarios(scenario_id) ON DELETE CASCADE,
    user_id           TEXT NOT NULL REFERENCES v2_user(user_id) ON DELETE CASCADE,
    num_trials        INT NOT NULL,
    created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    configuration     JSON NOT NULL DEFAULT '{}'
);

CREATE INDEX idx_scenario_runs_scenario_id_created_at
  ON v2_scenario_runs (scenario_id, created_at);

CREATE TABLE IF NOT EXISTS v2_trials (
    trial_id          TEXT PRIMARY KEY,
    scenario_run_id   TEXT NOT NULL REFERENCES v2_scenario_runs(scenario_run_id) ON DELETE CASCADE,
    scenario_id       TEXT NOT NULL REFERENCES v2_scenarios(scenario_id) ON DELETE CASCADE,

    thread_id         TEXT REFERENCES v2_thread(thread_id) ON DELETE SET NULL,

    index_in_run      INT NOT NULL,
    messages          JSON NOT NULL DEFAULT '[]',

    status            TEXT NOT NULL,
    created_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at        TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),

    status_updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    status_updated_by TEXT NOT NULL DEFAULT 'SYSTEM',

    error_message     TEXT,

    metadata        JSON NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_trials_run_id_index_in_run
  ON v2_trials (scenario_run_id, index_in_run);

CREATE INDEX IF NOT EXISTS idx_trials_status_created
  ON v2_trials (status, created_at)
  WHERE status = 'PENDING';