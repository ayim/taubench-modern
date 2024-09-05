ALTER TABLE checkpoints
ADD COLUMN metadata BYTEA;
-- added in langchain v0.1.7
CREATE TABLE IF NOT EXISTS writes (
    thread_id TEXT NOT NULL,
    thread_ts TIMESTAMP WITH TIME ZONE,
    task_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    channel TEXT NOT NULL,
    value BYTEA,
    PRIMARY KEY (thread_id, thread_ts, task_id, idx)
);