-- We use the uuid-ossp extension to generate UUIDs.
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create the v2 schema if it does not already exist
CREATE SCHEMA IF NOT EXISTS v2;

------------------------------------------------------------------------------
-- USERS
------------------------------------------------------------------------------
-- A "user" is a relatively lightweight concept in the system.
-- 'sub' is an external subject identifier (e.g., from JWT).
------------------------------------------------------------------------------
CREATE TABLE v2."user" (
    user_id   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sub       TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE 
               DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
);

CREATE INDEX idx_user_sub_v2 ON v2."user"(sub);

------------------------------------------------------------------------------
-- AGENTS
------------------------------------------------------------------------------
-- Agents are the core entity for "agent-server".
-- Each agent belongs to a user, and must have a unique name (case-insensitive) 
-- per user.
------------------------------------------------------------------------------
CREATE TABLE v2."agent" (
    agent_id    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     UUID NOT NULL,
    mode        VARCHAR(255) NOT NULL,
    name        VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    runbook     JSONB NOT NULL,
    version     VARCHAR(255) NOT NULL,
    updated_at  TIMESTAMP WITH TIME ZONE 
                DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    created_at  TIMESTAMP WITH TIME ZONE 
                DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    action_packages        JSONB NOT NULL,
    agent_architecture     JSONB NOT NULL,
    question_groups        JSONB NOT NULL,
    observability_configs  JSONB NOT NULL,
    provider_configs       JSONB NOT NULL,
    extra                  JSONB NOT NULL,

    CONSTRAINT fk_agent_user_id_v2
        FOREIGN KEY (user_id)
        REFERENCES v2."user" (user_id)
        ON DELETE CASCADE
);

-- Index on user_id for quick lookups of agents by user
CREATE INDEX idx_agent_user_id_v2 
    ON v2."agent"(user_id);

-- Ensure agent names are unique per user (case-insensitive)
CREATE UNIQUE INDEX idx_agent_name_per_user_v2 
    ON v2."agent"(user_id, LOWER(name));

------------------------------------------------------------------------------
-- THREADS
------------------------------------------------------------------------------
-- When conversing with an agent, each conversation occurs in a separate thread. 
-- A thread references a particular agent and user.
------------------------------------------------------------------------------
CREATE TABLE v2."thread" (
    thread_id  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id   UUID NOT NULL,
    user_id    UUID NOT NULL,
    name       VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE 
               DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    updated_at TIMESTAMP WITH TIME ZONE 
               DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    metadata   JSONB NOT NULL,
    CONSTRAINT fk_thread_agent_id_v2
        FOREIGN KEY (agent_id)
        REFERENCES v2."agent"(agent_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_thread_user_id_v2
        FOREIGN KEY (user_id)
        REFERENCES v2."user" (user_id)
        ON DELETE CASCADE
);

-- Indexes for quick lookups/filtering by agent or user
CREATE INDEX idx_thread_agent_id_v2 
    ON v2."thread"(agent_id);

CREATE INDEX idx_thread_user_id_v2 
    ON v2."thread"(user_id);

------------------------------------------------------------------------------
-- THREAD MESSAGES
------------------------------------------------------------------------------
-- Each thread has multiple messages, which can come from either the agent or 
-- the user. Content is stored in a JSONB array with a flexible schema.
------------------------------------------------------------------------------
CREATE TABLE v2."thread_message" (
    message_id    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sequence_number INT NOT NULL,
    thread_id     UUID NOT NULL,
    created_at    TIMESTAMP WITH TIME ZONE 
                  DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    updated_at    TIMESTAMP WITH TIME ZONE 
                  DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    role          VARCHAR(255) NOT NULL,  -- e.g., 'agent', 'user', 'system'
    content       JSONB NOT NULL,
    agent_metadata JSONB NOT NULL,
    server_metadata JSONB NOT NULL,
    CONSTRAINT fk_thread_messages_thread_id_v2
        FOREIGN KEY (thread_id)
        REFERENCES v2."thread"(thread_id)
        ON DELETE CASCADE
);

-- Index for quick retrieval of messages by thread
CREATE INDEX idx_thread_message_thread_id_v2 
    ON v2."thread_message"(thread_id);

------------------------------------------------------------------------------
-- RUNS
------------------------------------------------------------------------------
-- A run is a single invocation of an agent. The results of a run are often
-- new messages added to a thread, but we'll just focus on storing the run
-- and it's status / states here.
------------------------------------------------------------------------------
CREATE TABLE v2."agent_runs" (
    run_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL,
    thread_id UUID NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE 
               DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    finished_at TIMESTAMP WITH TIME ZONE 
               DEFAULT NULL,
    status VARCHAR(255) NOT NULL, -- e.g., 'running', 'completed', 'failed'
    metadata JSONB NOT NULL,
    run_type VARCHAR(255) NOT NULL, -- e.g., 'sync', 'async', 'stream'

    CONSTRAINT fk_agent_runs_agent_id_v2
      FOREIGN KEY (agent_id)
      REFERENCES v2."agent"(agent_id)
      ON DELETE CASCADE,
    CONSTRAINT fk_agent_runs_thread_id_v2
      FOREIGN KEY (thread_id)
      REFERENCES v2."thread"(thread_id)
      ON DELETE CASCADE
);

CREATE INDEX idx_agent_runs_agent_id_v2
    ON v2."agent_runs"(agent_id);

CREATE INDEX idx_agent_runs_thread_id_v2
    ON v2."agent_runs"(thread_id);

CREATE INDEX idx_agent_runs_status_v2
    ON v2."agent_runs"(status);


------------------------------------------------------------------------------
-- RUN STEPS
------------------------------------------------------------------------------
-- Run steps are the individual steps that make up a run.
-- Each step has an input state, an output state, and a status.
-- The input state is the state of the agent at the beginning of the step.
-- The output state is the state of the agent at the end of the step.
-- The status is the status of the step.
------------------------------------------------------------------------------
CREATE TABLE v2."agent_run_steps" (
    run_id UUID NOT NULL,
    step_id UUID NOT NULL PRIMARY KEY DEFAULT uuid_generate_v4(),
    step_status VARCHAR(255) NOT NULL, -- e.g., 'running', 'completed', 'failed'
    sequence_number INT NOT NULL,
    input_state_hash VARCHAR(255) NOT NULL,
    input_state JSONB NOT NULL,
    output_state_hash VARCHAR(255) NOT NULL,
    output_state JSONB NOT NULL,
    metadata JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE 
               DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    finished_at TIMESTAMP WITH TIME ZONE 
               DEFAULT NULL,
    
    CONSTRAINT fk_agent_run_steps_run_id_v2
      FOREIGN KEY (run_id)
      REFERENCES v2."agent_runs"(run_id)
      ON DELETE CASCADE
);

CREATE INDEX idx_agent_run_steps_run_id_v2
    ON v2."agent_run_steps"(run_id);

------------------------------------------------------------------------------
-- SCOPED STORAGE
------------------------------------------------------------------------------
-- A single table to store JSON data for different scopes (user, agent, thread, 
-- or global), identified by scope_type and scope_id. Each record also references 
-- who/what created it (via created_by_*).
------------------------------------------------------------------------------
CREATE TABLE v2."scoped_storage" (
    storage_id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    created_at           TIMESTAMP WITH TIME ZONE 
                         DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    updated_at           TIMESTAMP WITH TIME ZONE 
                         DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    created_by_user_id   UUID NOT NULL,
    created_by_agent_id  UUID NOT NULL,
    created_by_thread_id UUID NOT NULL,
    scope_type           VARCHAR(255) NOT NULL,  -- e.g. 'user', 'agent', 'thread', 'global'
    storage              JSONB NOT NULL,
    -- Let's add constraints so that we get cascading deletes
    CONSTRAINT fk_scoped_storage_created_by_user_id_v2
        FOREIGN KEY (created_by_user_id)
        REFERENCES v2."user"(user_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_scoped_storage_created_by_agent_id_v2
        FOREIGN KEY (created_by_agent_id)
        REFERENCES v2."agent"(agent_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_scoped_storage_created_by_thread_id_v2
        FOREIGN KEY (created_by_thread_id)
        REFERENCES v2."thread"(thread_id)
        ON DELETE CASCADE
);

-- Indexes for typical lookups on these columns
CREATE INDEX idx_scoped_storage_created_by_user_id_v2 
    ON v2."scoped_storage"(created_by_user_id);

CREATE INDEX idx_scoped_storage_created_by_agent_id_v2 
    ON v2."scoped_storage"(created_by_agent_id);

CREATE INDEX idx_scoped_storage_created_by_thread_id_v2 
    ON v2."scoped_storage"(created_by_thread_id);

CREATE INDEX idx_scoped_storage_scope_type_v2 
    ON v2."scoped_storage"(scope_type);

------------------------------------------------------------------------------
-- FILE OWNER
------------------------------------------------------------------------------
-- Tracks "file" records that may be associated with an agent or a thread. 
-- file_id is a text-based primary key. We also store optional references, 
-- file paths, etc.
------------------------------------------------------------------------------
CREATE TABLE v2."file_owner" (
    file_id             TEXT NOT NULL,
    file_ref            TEXT,
    file_path           TEXT NOT NULL,
    file_hash           TEXT,
    embedded            BOOLEAN,
    agent_id            UUID,
    thread_id           UUID,
    file_path_expiration TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (file_id),
    CONSTRAINT fk_file_owner_agent_id_v2
        FOREIGN KEY (agent_id)
        REFERENCES v2."agent"(agent_id)
        ON DELETE CASCADE,
    CONSTRAINT fk_file_owner_thread_id_v2
        FOREIGN KEY (thread_id)
        REFERENCES v2."thread"(thread_id)
        ON DELETE CASCADE,
    CONSTRAINT unique_file_ref_agent_v2
        UNIQUE (file_ref, agent_id),
    CONSTRAINT unique_file_ref_thread_v2
        UNIQUE (file_ref, thread_id)
);

-- Indexes for quick lookups
CREATE INDEX idx_file_owner_agent_id_v2 
    ON v2."file_owner"(agent_id);

CREATE INDEX idx_file_owner_thread_id_v2 
    ON v2."file_owner"(thread_id);

------------------------------------------------------------------------------
-- MEMORY
------------------------------------------------------------------------------
-- Represents stored "memories," each with some textual data, optional 
-- contextualization, relevant time frames, embedded metadata, etc.
------------------------------------------------------------------------------
CREATE TABLE v2."memory" (
    memory_id                TEXT PRIMARY KEY,
    original_text            TEXT NOT NULL,
    contextualized_text      TEXT,
    created_at               TIMESTAMP WITH TIME ZONE 
                             DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    updated_at               TIMESTAMP WITH TIME ZONE 
                             DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    relevant_until_timestamp TIMESTAMP WITH TIME ZONE,
    relevant_after_timestamp TIMESTAMP WITH TIME ZONE,
    scope                    VARCHAR(255) NOT NULL,  -- e.g. 'user', 'agent', 'thread', etc.
    metadata                 JSONB NOT NULL,
    tags                     JSONB NOT NULL,
    refs                     JSONB NOT NULL,
    weight                   FLOAT NOT NULL DEFAULT 1.0,
    embedded                 BOOLEAN NOT NULL DEFAULT false,
    embedding_id             UUID -- references some external embedding resource
);

CREATE INDEX idx_memory_scope_v2 
    ON v2."memory"(scope);

------------------------------------------------------------------------------
-- CHECK USER ACCESS
------------------------------------------------------------------------------
-- Convenience function to check if a user has access to a record.
------------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION v2.check_user_access(record_user_id UUID, requesting_user_id UUID) 
RETURNS BOOLEAN AS $$
BEGIN
    RETURN record_user_id = requesting_user_id OR 
           EXISTS (SELECT 1 FROM v2.user u 
                  WHERE requesting_user_id = u.user_id 
                  AND u.sub LIKE 'tenant:%:system:system_user');
END;
$$ LANGUAGE plpgsql;
