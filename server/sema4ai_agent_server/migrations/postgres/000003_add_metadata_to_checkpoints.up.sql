-- langchain v0.2.0 sets checkpoint['id'] to thread_ts so all timestamp fields must
-- actually support text. These do monocrementally increment so then can still be sorted, but
-- they are not actually timestamps.
-- 
-- Step 1: Create a new table with the new schema
CREATE TABLE IF NOT EXISTS new_checkpoints (
    thread_id TEXT NOT NULL,
    thread_ts TEXT NOT NULL,
    parent_ts TEXT,
    checkpoint BYTEA,
    metadata BYTEA,
    PRIMARY KEY (thread_id, thread_ts)
);
-- Step 2: Copy the data from the old table to the new table
INSERT INTO new_checkpoints (
        thread_id,
        thread_ts,
        parent_ts,
        checkpoint,
        metadata
    )
SELECT thread_id,
    thread_ts,
    thread_ts,
    checkpoint,
    '{}'::BYTEA
FROM checkpoints;
-- Step 3: Drop the old table and rename the new table
DROP TABLE checkpoints;
-- Step 4: Rename the new table
ALTER TABLE new_checkpoints
    RENAME TO checkpoints;
-- writes table added in langchain v0.1.7
CREATE TABLE IF NOT EXISTS writes (
    thread_id TEXT NOT NULL,
    thread_ts TEXT NOT NULL,
    task_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    channel TEXT NOT NULL,
    value BYTEA,
    PRIMARY KEY (thread_id, thread_ts, task_id, idx)
);