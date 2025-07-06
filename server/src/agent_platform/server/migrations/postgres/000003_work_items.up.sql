CREATE TABLE IF NOT EXISTS v2.work_items (
    work_item_id       UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    user_id            UUID NOT NULL
                           REFERENCES v2.user(user_id)   ON DELETE CASCADE,
    agent_id           UUID NOT NULL
                           REFERENCES v2.agent(agent_id) ON DELETE CASCADE,
    thread_id          UUID
                           REFERENCES v2.thread(thread_id) ON DELETE SET NULL,

    status             TEXT NOT NULL DEFAULT 'PENDING',
    created_at         TIMESTAMPTZ NOT NULL
                           DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    updated_at         TIMESTAMPTZ NOT NULL
                           DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    completed_by       TEXT,
    status_updated_at  TIMESTAMPTZ NOT NULL
                           DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    status_updated_by  TEXT NOT NULL DEFAULT 'SYSTEM',

    messages           JSONB NOT NULL,
    payload            JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_work_items_status          ON v2.work_items(status);
CREATE INDEX IF NOT EXISTS idx_work_items_created_at      ON v2.work_items(created_at);
CREATE INDEX IF NOT EXISTS idx_work_items_status_created  ON v2.work_items(status, created_at)
                                                          WHERE status = 'PENDING';
