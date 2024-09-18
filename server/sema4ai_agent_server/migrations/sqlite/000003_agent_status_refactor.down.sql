CREATE TABLE agent_temp (
    id TEXT PRIMARY KEY NOT NULL,
    user_id TEXT NOT NULL,
    status TEXT NOT NULL,
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
    id, user_id, status, name, description, runbook, version, 
    updated_at, metadata, model, architecture, reasoning, 
    action_packages, public
)
SELECT 
    id, user_id, 'ready' AS status, name, description, runbook, version, 
    updated_at, metadata, model, architecture, reasoning, 
    action_packages, public
FROM agent;

DROP TABLE agent;
ALTER TABLE agent_temp RENAME TO agent;

CREATE TABLE file_owners_temp (
    file_id TEXT NOT NULL,
    file_ref TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    embedded BOOLEAN NOT NULL,
    agent_id TEXT,
    thread_id TEXT,
    file_path_expiration DATETIME,
    PRIMARY KEY (file_id),
    FOREIGN KEY (agent_id) REFERENCES agent(id) ON DELETE SET NULL,
    FOREIGN KEY (thread_id) REFERENCES thread(thread_id) ON DELETE SET NULL,
    CONSTRAINT unique_file_ref_agent UNIQUE (file_ref, agent_id),
    CONSTRAINT unique_file_ref_thread UNIQUE (file_ref, thread_id)
);

INSERT INTO file_owners_temp (
    file_id, file_ref, file_path, file_hash, embedded, 
    agent_id, thread_id, file_path_expiration
)
SELECT 
    file_id, file_ref, file_path, file_hash, embedded, 
    agent_id, thread_id, file_path_expiration
FROM file_owners;

DROP TABLE file_owners;
ALTER TABLE file_owners_temp RENAME TO file_owners;