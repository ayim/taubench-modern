PRAGMA foreign_keys = ON;

------------------------------------------------------------------------------
-- USERS
------------------------------------------------------------------------------
-- A "user" is a relatively lightweight concept in the system.
-- 'sub' is an external subject identifier (e.g., from JWT).
------------------------------------------------------------------------------
CREATE TABLE v2_user (
    user_id TEXT PRIMARY KEY,
    sub     TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_user_sub_v2 ON v2_user(sub);

------------------------------------------------------------------------------
-- AGENTS
------------------------------------------------------------------------------
-- Agents are the core entity for "agent-server".
-- Each agent belongs to a user, and must have a unique name (case-insensitive) 
-- per user.
------------------------------------------------------------------------------
CREATE TABLE v2_agent (
    agent_id    TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    mode        TEXT NOT NULL,
    name        TEXT NOT NULL,
    description TEXT NOT NULL,
    runbook     TEXT NOT NULL CHECK (json_valid(runbook)),
    version     TEXT NOT NULL,
    updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    action_packages       TEXT NOT NULL CHECK (json_valid(action_packages)),
    agent_architecture    TEXT NOT NULL CHECK (json_valid(agent_architecture)),
    question_groups       TEXT NOT NULL CHECK (json_valid(question_groups)),
    observability_configs TEXT NOT NULL CHECK (json_valid(observability_configs)),
    provider_configs      TEXT NOT NULL CHECK (json_valid(provider_configs)),
    extra                 TEXT NOT NULL CHECK (json_valid(extra)),

    CONSTRAINT fk_agent_user_id
      FOREIGN KEY (user_id)
      REFERENCES v2_user (user_id)
      ON DELETE CASCADE
);

-- Index on user_id for quick lookups of agents by user
CREATE INDEX idx_agent_user_id_v2
    ON v2_agent(user_id);

-- Ensure agent names are unique per user (case-insensitive)
CREATE UNIQUE INDEX idx_agent_name_per_user_v2
    ON v2_agent(user_id, lower(name));

------------------------------------------------------------------------------
-- THREADS
------------------------------------------------------------------------------
-- When conversing with an agent, each conversation occurs in a separate thread. 
-- A thread references a particular agent and user.
------------------------------------------------------------------------------
CREATE TABLE v2_thread (
    thread_id  TEXT PRIMARY KEY,
    agent_id   TEXT NOT NULL,
    user_id    TEXT NOT NULL,
    name       TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    metadata   TEXT NOT NULL CHECK (json_valid(metadata)),

    CONSTRAINT fk_thread_agent_id
      FOREIGN KEY (agent_id)
      REFERENCES v2_agent(agent_id)
      ON DELETE CASCADE,
    CONSTRAINT fk_thread_user_id
      FOREIGN KEY (user_id)
      REFERENCES v2_user(user_id)
      ON DELETE CASCADE
);

-- Indexes for quick lookups/filtering by agent or user
CREATE INDEX idx_thread_agent_id_v2
    ON v2_thread(agent_id);

CREATE INDEX idx_thread_user_id_v2
    ON v2_thread(user_id);

------------------------------------------------------------------------------
-- THREAD MESSAGES
------------------------------------------------------------------------------
-- Each thread has multiple messages, which can come from either the agent or 
-- the user. Content is stored in a JSONB array with a flexible schema.
------------------------------------------------------------------------------
CREATE TABLE v2_thread_message (
    message_id    TEXT PRIMARY KEY,
    sequence_number INT NOT NULL,
    thread_id     TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),
    role          TEXT NOT NULL,  -- e.g., 'agent', 'user', 'system'
    content       TEXT NOT NULL CHECK (json_valid(content)),
    agent_metadata   TEXT NOT NULL CHECK (json_valid(agent_metadata)),
    server_metadata TEXT NOT NULL CHECK (json_valid(server_metadata)),

    CONSTRAINT fk_thread_messages_thread_id_v2
      FOREIGN KEY (thread_id)
      REFERENCES v2_thread(thread_id)
      ON DELETE CASCADE
);

-- Index for quick retrieval of messages by thread
CREATE INDEX idx_thread_message_thread_id_v2
    ON v2_thread_message(thread_id);

------------------------------------------------------------------------------
-- RUNS
------------------------------------------------------------------------------
-- A run is a single invocation of an agent. The results of a run are often
-- new messages added to a thread, but we'll just focus on storing the run
-- and it's status / states here.
------------------------------------------------------------------------------
CREATE TABLE v2_agent_runs (
    run_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT DEFAULT NULL,
    status TEXT NOT NULL, -- e.g., 'running', 'completed', 'failed'
    metadata TEXT NOT NULL CHECK (json_valid(metadata)),
    run_type TEXT NOT NULL, -- e.g., 'sync', 'async', 'stream'

    CONSTRAINT fk_agent_runs_agent_id_v2
      FOREIGN KEY (agent_id)
      REFERENCES v2_agent(agent_id)
      ON DELETE CASCADE,
    CONSTRAINT fk_agent_runs_thread_id_v2
      FOREIGN KEY (thread_id)
      REFERENCES v2_thread(thread_id)
      ON DELETE CASCADE
);

CREATE INDEX idx_agent_runs_agent_id_v2
    ON v2_agent_runs(agent_id);

CREATE INDEX idx_agent_runs_thread_id_v2
    ON v2_agent_runs(thread_id);

CREATE INDEX idx_agent_runs_status_v2
    ON v2_agent_runs(status);


------------------------------------------------------------------------------
-- RUN STEPS
------------------------------------------------------------------------------
-- Run steps are the individual steps that make up a run.
-- Each step has an input state, an output state, and a status.
-- The input state is the state of the agent at the beginning of the step.
-- The output state is the state of the agent at the end of the step.
-- The status is the status of the step.
------------------------------------------------------------------------------
CREATE TABLE v2_agent_run_steps (
    run_id TEXT NOT NULL,
    step_id TEXT NOT NULL PRIMARY KEY,
    step_status TEXT NOT NULL, -- e.g., 'running', 'completed', 'failed'
    sequence_number INT NOT NULL,
    input_state_hash TEXT NOT NULL,
    input_state TEXT NOT NULL CHECK (json_valid(input_state)),
    output_state_hash TEXT NOT NULL,
    output_state TEXT NOT NULL CHECK (json_valid(output_state)),
    metadata TEXT NOT NULL CHECK (json_valid(metadata)),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT DEFAULT NULL,
    
    CONSTRAINT fk_agent_run_steps_run_id_v2
      FOREIGN KEY (run_id)
      REFERENCES v2_agent_runs(run_id)
      ON DELETE CASCADE
);

CREATE INDEX idx_agent_run_steps_run_id_v2
    ON v2_agent_run_steps(run_id);

------------------------------------------------------------------------------
-- SCOPED STORAGE
------------------------------------------------------------------------------
-- A single table to store JSON data for different scopes (user, agent, thread, 
-- or global), identified by scope_type and scope_id. Each record also references 
-- who/what created it (via created_by_*).
------------------------------------------------------------------------------
CREATE TABLE v2_scoped_storage (
    storage_id           TEXT PRIMARY KEY,
    created_at           TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at           TEXT NOT NULL DEFAULT (datetime('now')),
    created_by_user_id   TEXT NOT NULL,
    created_by_agent_id  TEXT NOT NULL,
    created_by_thread_id TEXT NOT NULL,
    scope_type           TEXT NOT NULL,  -- e.g. 'user', 'agent', 'thread', 'global'
    storage              TEXT NOT NULL CHECK (json_valid(storage)),

    CONSTRAINT fk_scoped_storage_created_by_user_id
      FOREIGN KEY (created_by_user_id)
      REFERENCES v2_user(user_id)
      ON DELETE CASCADE,
    CONSTRAINT fk_scoped_storage_created_by_agent_id
      FOREIGN KEY (created_by_agent_id)
      REFERENCES v2_agent(agent_id)
      ON DELETE CASCADE,
    CONSTRAINT fk_scoped_storage_created_by_thread_id
      FOREIGN KEY (created_by_thread_id)
      REFERENCES v2_thread(thread_id)
      ON DELETE CASCADE
);

-- Indexes for typical lookups on these columns
CREATE INDEX idx_scoped_storage_created_by_user_id 
    ON v2_scoped_storage(created_by_user_id);

CREATE INDEX idx_scoped_storage_created_by_agent_id 
    ON v2_scoped_storage(created_by_agent_id);

CREATE INDEX idx_scoped_storage_created_by_thread_id 
    ON v2_scoped_storage(created_by_thread_id);

CREATE INDEX idx_scoped_storage_scope_type 
    ON v2_scoped_storage(scope_type);

------------------------------------------------------------------------------
-- FILE OWNER
------------------------------------------------------------------------------
-- Tracks "file" records that may be associated with an agent or a thread. 
-- file_id is a text-based primary key. We also store optional references, 
-- file paths, etc.
------------------------------------------------------------------------------
CREATE TABLE v2_file_owner
(
    file_id TEXT PRIMARY KEY,
    file_ref TEXT,
    file_path TEXT NOT NULL,
    file_hash TEXT,
    file_size_raw INTEGER,
    -- Added: Raw file size in bytes
    mime_type TEXT,
    -- Added: MIME type of the file
    user_id TEXT,
    -- Added: Reference to v2_user
    embedded BOOLEAN,
    agent_id TEXT,
    thread_id TEXT,
    file_path_expiration TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    CONSTRAINT fk_file_owner_agent_id
      FOREIGN KEY (agent_id)
      REFERENCES v2_agent(agent_id)
      ON DELETE CASCADE,
    CONSTRAINT fk_file_owner_thread_id
      FOREIGN KEY (thread_id)
      REFERENCES v2_thread(thread_id)
      ON DELETE CASCADE,
    CONSTRAINT fk_file_owner_user_id    -- Added: Foreign key constraint for user_id
      FOREIGN KEY (user_id)
      REFERENCES v2_user(user_id)
      ON DELETE CASCADE,
    CONSTRAINT unique_file_ref_agent
      UNIQUE (file_ref, agent_id),
    CONSTRAINT unique_file_ref_thread
      UNIQUE (file_ref, thread_id)
);

-- Indexes for quick lookups
CREATE INDEX idx_file_owner_agent_id 
    ON v2_file_owner(agent_id);

CREATE INDEX idx_file_owner_thread_id 
    ON v2_file_owner(thread_id);

-- Add index for user_id lookups
CREATE INDEX idx_file_owner_user_id 
    ON v2_file_owner(user_id);

------------------------------------------------------------------------------
-- MEMORY
------------------------------------------------------------------------------
-- Represents stored "memories," each with some textual data, optional 
-- contextualization, relevant time frames, embedded metadata, etc.
------------------------------------------------------------------------------
CREATE TABLE v2_memory (
    memory_id                TEXT PRIMARY KEY,
    original_text            TEXT NOT NULL,
    contextualized_text      TEXT,
    created_at               TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at               TEXT NOT NULL DEFAULT (datetime('now')),
    relevant_until_timestamp TEXT,
    relevant_after_timestamp TEXT,
    scope                    TEXT NOT NULL,  -- e.g. 'user', 'agent', 'thread', etc.
    metadata                 TEXT NOT NULL CHECK (json_valid(metadata)),
    tags                     TEXT NOT NULL CHECK (json_valid(tags)),
    refs                     TEXT NOT NULL CHECK (json_valid(refs)),
    weight                   REAL NOT NULL DEFAULT 1.0,
    embedded                 BOOLEAN NOT NULL DEFAULT 0,
    embedding_id             TEXT
);

CREATE INDEX idx_memory_scope 
    ON v2_memory(scope);

------------------------------------------------------------------------------
-- CHECK USER ACCESS
------------------------------------------------------------------------------
-- Can't implement this in SQL in SQLite, so we'll do it on the Python side.
------------------------------------------------------------------------------
