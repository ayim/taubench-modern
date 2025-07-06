CREATE TABLE IF NOT EXISTS v2_work_items (
    work_item_id TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL
                   REFERENCES v2_user(user_id)  ON DELETE CASCADE,
    agent_id     TEXT NOT NULL
                   REFERENCES v2_agent(agent_id) ON DELETE CASCADE,
    thread_id    TEXT
                   REFERENCES v2_thread(thread_id) ON DELETE SET NULL,

    status            TEXT NOT NULL,
    created_at        TEXT NOT NULL
                          DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at        TEXT NOT NULL
                          DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    completed_by      TEXT,
    status_updated_at TEXT NOT NULL
                          DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    status_updated_by TEXT NOT NULL DEFAULT 'SYSTEM',

    messages TEXT NOT NULL,   -- JSON serialised
    payload  TEXT NOT NULL    -- JSON serialised
);

CREATE INDEX IF NOT EXISTS idx_work_items_status          ON v2_work_items(status);
CREATE INDEX IF NOT EXISTS idx_work_items_created_at      ON v2_work_items(created_at);
CREATE INDEX IF NOT EXISTS idx_work_items_status_created  ON v2_work_items(status, created_at)
                                                          WHERE status = 'PENDING';
