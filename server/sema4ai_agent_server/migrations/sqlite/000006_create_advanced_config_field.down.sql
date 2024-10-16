BEGIN TRANSACTION;
-- Step 1: Create a new table with the original schema
CREATE TABLE agent_old (
    id TEXT PRIMARY KEY NOT NULL,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL UNIQUE COLLATE NOCASE,
    description TEXT NOT NULL,
    runbook TEXT NOT NULL,
    version TEXT NOT NULL,
    updated_at DATETIME DEFAULT (datetime('now')),
    metadata TEXT NOT NULL,
    model TEXT,
    architecture TEXT NOT NULL,
    reasoning TEXT NOT NULL,
    action_packages TEXT,
    public BOOLEAN NOT NULL DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES "user" (user_id)
);
-- Step 2: Copy data from the current table to the new table, transforming the data as needed
INSERT INTO agent_old (
        id,
        user_id,
        name,
        description,
        runbook,
        version,
        updated_at,
        metadata,
        model,
        architecture,
        reasoning,
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
    -- Extract 'architecture' and 'reasoning' from 'advanced_config' JSON
    json_extract(advanced_config, '$.architecture') AS architecture,
    json_extract(advanced_config, '$.reasoning') AS reasoning,
    action_packages,
    public
FROM agent;
-- Step 3: Drop the current table
DROP TABLE agent;
-- Step 4: Rename the new table to the original table's name
ALTER TABLE agent_old
    RENAME TO agent;
-- Commit the transaction to make changes permanent
COMMIT;