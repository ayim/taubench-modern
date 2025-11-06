PRAGMA foreign_keys = ON;

CREATE TABLE v2_file_owner_tmp
(
    file_id TEXT PRIMARY KEY,
    file_ref TEXT,
    file_path TEXT,
    file_hash TEXT,
    file_size_raw INTEGER,
    mime_type TEXT,
    user_id TEXT,
    embedded BOOLEAN,
    agent_id TEXT,
    thread_id TEXT,
    work_item_id TEXT,
    scenario_id TEXT,
    file_path_expiration TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

    CONSTRAINT fk_file_owner_agent_id
      FOREIGN KEY (agent_id)
      REFERENCES v2_agent(agent_id)
      ON DELETE CASCADE,
    CONSTRAINT fk_file_owner_thread_id
      FOREIGN KEY (thread_id)
      REFERENCES v2_thread(thread_id)
      ON DELETE CASCADE,
    CONSTRAINT fk_file_owner_user_id
      FOREIGN KEY (user_id)
      REFERENCES v2_user(user_id)
      ON DELETE CASCADE,
    CONSTRAINT fk_file_owner_work_item_id
      FOREIGN KEY (work_item_id)
      REFERENCES v2_work_items(work_item_id)
      ON DELETE CASCADE,
    CONSTRAINT fk_file_owner_scenario_id
      FOREIGN KEY (scenario_id)
      REFERENCES v2_scenarios(scenario_id)
      ON DELETE CASCADE,
    CONSTRAINT unique_file_ref_thread
      UNIQUE (file_ref, thread_id),
    CONSTRAINT unique_file_ref_scenario
      UNIQUE (file_ref, scenario_id)
);

INSERT INTO v2_file_owner_tmp(
    file_id,
    file_ref,
    file_path,
    file_hash,
    file_size_raw,
    mime_type,
    user_id,
    embedded,
    agent_id,
    thread_id,
    work_item_id,
    file_path_expiration,
    created_at
)
SELECT
    file_id,
    file_ref,
    file_path,
    file_hash,
    file_size_raw,
    mime_type,
    user_id,
    embedded,
    agent_id,
    thread_id,
    work_item_id,
    file_path_expiration,
    created_at
FROM v2_file_owner;

DROP TABLE v2_file_owner;
ALTER TABLE v2_file_owner_tmp RENAME TO v2_file_owner;

CREATE INDEX idx_file_owner_agent_id ON v2_file_owner(agent_id);
CREATE INDEX idx_file_owner_thread_id ON v2_file_owner(thread_id);
CREATE INDEX idx_file_owner_user_id ON v2_file_owner(user_id);
CREATE INDEX idx_file_owner_work_item_id ON v2_file_owner(work_item_id);
CREATE INDEX idx_file_owner_scenario_id ON v2_file_owner(scenario_id);
