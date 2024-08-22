-- Legacy: hard resetting the database (can be removed in the future)
DROP TABLE IF EXISTS file_owners;
DROP TABLE IF EXISTS checkpoints;
DROP TABLE IF EXISTS thread;
DROP TABLE IF EXISTS agent;
DROP TABLE IF EXISTS "user";
DROP TABLE IF EXISTS migration_version;
-- End of legacy

CREATE TABLE "user" (
    user_id TEXT PRIMARY KEY,
    sub TEXT UNIQUE NOT NULL,
    created_at DATETIME DEFAULT (datetime('now'))
);

CREATE TABLE agent (
    id TEXT PRIMARY KEY NOT NULL,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    config TEXT NOT NULL,
    updated_at DATETIME DEFAULT (datetime('now')),
    public BOOLEAN NOT NULL CHECK (public IN (0,1)),
    metadata TEXT,
    model TEXT,
    architecture TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES "user" (user_id)
);

CREATE TABLE thread (
    thread_id TEXT PRIMARY KEY NOT NULL,
    agent_id TEXT,
    user_id TEXT NOT NULL,
    name TEXT NOT NULL,
    updated_at DATETIME DEFAULT (datetime('now')),
    metadata TEXT,
    FOREIGN KEY (agent_id) REFERENCES agent(id) ON DELETE SET NULL,
    FOREIGN KEY (user_id) REFERENCES "user" (user_id)
);

CREATE TABLE checkpoints (
    thread_id TEXT NOT NULL,
    thread_ts DATETIME NOT NULL,
    parent_ts DATETIME,
    checkpoint BLOB,
    PRIMARY KEY (thread_id, thread_ts)
);

CREATE TABLE file_owners (
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

CREATE TABLE async_runs (
    id TEXT PRIMARY KEY NOT NULL,
    status TEXT NOT NULL
)