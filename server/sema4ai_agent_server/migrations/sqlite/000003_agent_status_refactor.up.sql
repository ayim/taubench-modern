CREATE TABLE agent_temp (
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

INSERT INTO agent_temp (
    id, user_id, name, description, runbook, version, updated_at, 
    metadata, model, architecture, reasoning, action_packages, 
    public
)
SELECT 
    id, user_id, name, description, runbook, version, updated_at, 
    metadata, model, architecture, reasoning, action_packages, 
    public
FROM agent;

DROP TABLE agent;
ALTER TABLE agent_temp RENAME TO agent;

ALTER TABLE file_owners
ADD COLUMN embedding_status TEXT DEFAULT NULL;
UPDATE file_owners
SET embedding_status = 'success'
WHERE embedded = TRUE;