-- introduced in langchain v0.2.0
ALTER TABLE checkpoints
ADD COLUMN metadata BLOB;
-- added in langchain v0.1.7
CREATE TABLE IF NOT EXISTS writes (
    thread_id TEXT NOT NULL,
    thread_ts TEXT NOT NULL,
    task_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    channel TEXT NOT NULL,
    value BLOB,
    PRIMARY KEY (thread_id, thread_ts, task_id, idx)
);