-- Legacy: hard resetting the database (can be removed in the future)
DROP TABLE IF EXISTS file_owners;
DROP TABLE IF EXISTS checkpoints;
DROP TABLE IF EXISTS thread;
DROP TABLE IF EXISTS agent;
DROP TABLE IF EXISTS "user";
DROP TABLE IF EXISTS schema_migrations;
-- End of legacy

CREATE TABLE "user" (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    sub VARCHAR(255) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
);

CREATE TABLE agent (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    runbook TEXT NOT NULL,
    version VARCHAR(255) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    metadata JSONB,
    model JSONB,
    architecture TEXT NOT NULL,
    reasoning TEXT NOT NULL,
    action_packages JSONB,
    CONSTRAINT fk_agent_user_id FOREIGN KEY (user_id) REFERENCES "user"(user_id)
);

CREATE TABLE thread (
    thread_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID,
    user_id UUID NOT NULL,
    name VARCHAR(255) NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    metadata JSONB,
    CONSTRAINT fk_thread_agent_id FOREIGN KEY (agent_id) REFERENCES agent(id) ON DELETE SET NULL,
    CONSTRAINT fk_thread_user_id FOREIGN KEY (user_id) REFERENCES "user"(user_id)
);

CREATE TABLE checkpoints (
    thread_id TEXT,
    thread_ts TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    parent_ts TIMESTAMP WITH TIME ZONE,
    checkpoint BYTEA,
    PRIMARY KEY (thread_id, thread_ts)
);

CREATE TABLE file_owners (
    file_id TEXT NOT NULL,
    file_ref TEXT,
    file_path TEXT NOT NULL,
    file_hash TEXT,
    embedded BOOLEAN,
    agent_id UUID,
    thread_id UUID,
    file_path_expiration TIMESTAMP WITH TIME ZONE,
    PRIMARY KEY (file_id),
    FOREIGN KEY (agent_id) REFERENCES agent(id) ON DELETE SET NULL,
    FOREIGN KEY (thread_id) REFERENCES thread(thread_id) ON DELETE SET NULL,
    CONSTRAINT unique_file_ref_agent UNIQUE (file_ref, agent_id),
    CONSTRAINT unique_file_ref_thread UNIQUE (file_ref, thread_id)
);

CREATE TABLE async_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    status VARCHAR(20) NOT NULL
)