PRAGMA foreign_keys = OFF;

-- Restore the original v2_file_owner table
CREATE TABLE v2_file_owner_restore
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
    CONSTRAINT fk_file_owner_thread_id
      FOREIGN KEY (thread_id)
      REFERENCES v2_thread(thread_id)
    CONSTRAINT fk_file_owner_user_id
      FOREIGN KEY (user_id)
      REFERENCES v2_user(user_id)
    CONSTRAINT unique_file_ref_agent
      UNIQUE (file_ref, agent_id)
    CONSTRAINT unique_file_ref_thread
      UNIQUE (file_ref, thread_id)
);

-- Copy over rows from v2_file_owner to v2_file_owner_tmp
insert into v2_file_owner_restore(file_id, file_ref, file_path, file_hash, file_size_raw, mime_type, user_id, embedded, agent_id, thread_id, file_path_expiration, created_at)
    select file_id, file_ref, file_path, file_hash, file_size_raw, mime_type, user_id, embedded, agent_id, thread_id, file_path_expiration, created_at
    from v2_file_owner;

-- Drop the current v2_file_owner table
drop table v2_file_owner;

-- Drop the indexes so that we can recreate them later
drop index if exists idx_file_owner_agent_id;
drop index if exists idx_file_owner_thread_id;
drop index if exists idx_file_owner_user_id;

-- Move the restored table to the original name
alter table v2_file_owner_restore rename to v2_file_owner;

-- Recreate the indexes for quick lookups now that the new table is in the proper place
CREATE INDEX idx_file_owner_agent_id ON v2_file_owner(agent_id);
CREATE INDEX idx_file_owner_thread_id ON v2_file_owner(thread_id);
CREATE INDEX idx_file_owner_user_id ON v2_file_owner(user_id);

PRAGMA foreign_keys = ON;