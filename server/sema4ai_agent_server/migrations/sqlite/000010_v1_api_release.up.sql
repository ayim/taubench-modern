-- Rename the "assistant" table to "agent" and "assistant_id" to "id"
CREATE TABLE agent (
    id TEXT PRIMARY KEY NOT NULL,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    config TEXT NOT NULL,
    updated_at DATETIME DEFAULT (datetime('now')),
    public BOOLEAN NOT NULL CHECK (public IN (0,1)),
    metadata TEXT
);
INSERT INTO agent (id, user_id, name, config, updated_at, public, metadata)
SELECT assistant_id, user_id, name, config, updated_at, public, metadata
FROM assistant;
DROP TABLE assistant;

-- Rename "assistant_id" to "agent_id" in the "thread" table
CREATE TABLE thread_temp (
    thread_id TEXT PRIMARY KEY NOT NULL,
    agent_id TEXT,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    updated_at DATETIME DEFAULT (datetime('now')),
    metadata TEXT,
    FOREIGN KEY (agent_id) REFERENCES agent(id) ON DELETE SET NULL
);
INSERT INTO thread_temp (thread_id, agent_id, user_id, name, updated_at, metadata)
SELECT thread_id, assistant_id, user_id, name, updated_at, metadata
FROM thread;
DROP TABLE thread;
ALTER TABLE thread_temp RENAME TO thread;

-- Rename "assistant_id" to "agent_id" in the "file_owners" table
CREATE TABLE file_owners_temp (
    file_id TEXT NOT NULL,
    file_ref TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    embedded BOOLEAN NOT NULL,
    agent_id TEXT, -- Renamed from assistant_id
    thread_id TEXT,
    file_path_expiration DATETIME,
    PRIMARY KEY (file_id),
    FOREIGN KEY (agent_id) REFERENCES agent(id) ON DELETE SET NULL,
    FOREIGN KEY (thread_id) REFERENCES thread(thread_id) ON DELETE SET NULL,
    CONSTRAINT unique_file_ref_agent UNIQUE (file_ref, agent_id),
    CONSTRAINT unique_file_ref_thread UNIQUE (file_ref, thread_id)
);
INSERT INTO file_owners_temp (
    file_id,
    file_ref,
    file_path,
    file_hash,
    embedded,
    agent_id, -- Insert data into the renamed column
    thread_id,
    file_path_expiration
)
SELECT
    file_id,
    file_ref,
    file_path,
    file_hash,
    embedded,
    assistant_id, -- Select data from the old column
    thread_id,
    file_path_expiration
FROM file_owners;
DROP TABLE file_owners;
ALTER TABLE file_owners_temp RENAME TO file_owners;
