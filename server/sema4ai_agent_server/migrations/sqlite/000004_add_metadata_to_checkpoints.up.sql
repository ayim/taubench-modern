-- langchain v0.3.0 modifies the checkpoint schema significantly. Backwards compatibility is
-- not guaranteed.
-- 
-- Step 1: Create a new table with the new schema
CREATE TABLE IF NOT EXISTS new_checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    checkpoint BLOB,
    metadata BLOB,
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);
-- Step 2: Copy the data from the old table to the new table
INSERT INTO new_checkpoints (
        thread_id,
        checkpoint_id,
        -- was thread_ts
        parent_checkpoint_id,
        -- was parent_ts
        checkpoint,
        metadata
    )
SELECT thread_id,
    thread_ts,
    parent_ts,
    checkpoint,
    CAST('{}' AS BLOB)
FROM checkpoints;
-- Step 3: Drop the old table and rename the new table
DROP TABLE checkpoints;
-- Step 4: Rename the new table
ALTER TABLE new_checkpoints
    RENAME TO checkpoints;
-- writes table added in langchain v0.1.7
CREATE TABLE IF NOT EXISTS writes (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    channel TEXT NOT NULL,
    value BLOB,
    PRIMARY KEY (
        thread_id,
        checkpoint_ns,
        checkpoint_id,
        task_id,
        idx
    )
);
-- Remove existing vector stores and embeddings
DROP TABLE IF EXISTS langchain_pg_collection;
DROP TABLE IF EXISTS langchain_pg_embedding;