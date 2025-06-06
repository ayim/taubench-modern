PRAGMA foreign_keys = ON;


-- Create a copy of v2_file_owner without the unique constraint on file_ref, agent_id 
CREATE TABLE v2_file_owner_tmp
(
    file_id TEXT PRIMARY KEY,
    file_ref TEXT,
    file_path TEXT,
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
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),

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
    CONSTRAINT unique_file_ref_thread
      UNIQUE (file_ref, thread_id)
);

-- Copy over rows from v2_file_owner to v2_file_owner_tmp
insert into v2_file_owner_tmp(file_id, file_ref, file_path, file_hash, file_size_raw, mime_type, user_id, embedded, agent_id, thread_id, file_path_expiration, created_at)
    select file_id, file_ref, file_path, file_hash, file_size_raw, mime_type, user_id, embedded, agent_id, thread_id, file_path_expiration, created_at
    from v2_file_owner;

-- Rename v2_file_owner to v2_file_owner_old
alter table v2_file_owner rename to v2_file_owner_old;

-- Rename v2_file_owner_tmp to v2_file_owner
alter table v2_file_owner_tmp rename to v2_file_owner;