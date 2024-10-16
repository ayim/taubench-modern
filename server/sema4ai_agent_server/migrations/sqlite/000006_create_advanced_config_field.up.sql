BEGIN TRANSACTION;
-- Step 1: Create a new table with the desired schema
CREATE TABLE agent_new (
    id TEXT PRIMARY KEY NOT NULL,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    description TEXT NOT NULL,
    runbook TEXT NOT NULL,
    version TEXT NOT NULL,
    updated_at DATETIME DEFAULT (datetime('now')),
    metadata TEXT NOT NULL,
    model TEXT,
    advanced_config TEXT NOT NULL,
    action_packages TEXT,
    public BOOLEAN NOT NULL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES "user" (user_id)
);
-- Step 2: Copy data from the old table to the new table, transforming the data as needed
INSERT INTO agent_new (
        id,
        user_id,
        name,
        description,
        runbook,
        version,
        updated_at,
        metadata,
        model,
        advanced_config,
        action_packages,
        public
    )
SELECT id,
    user_id,
    name,
    description,
    runbook,
    version,
    updated_at,
    metadata,
    model,
    json_object(
        'architecture',
        architecture,
        'reasoning',
        reasoning
    ) AS advanced_config,
    action_packages,
    public
FROM agent;
-- Step 3: Drop the old table
DROP TABLE agent;
-- Step 4: Rename the new table to the old table's name
ALTER TABLE agent_new
    RENAME TO agent;
-- Commit the transaction to make changes permanent
COMMIT;