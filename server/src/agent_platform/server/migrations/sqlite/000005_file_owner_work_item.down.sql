PRAGMA foreign_keys = ON;

-- Reverse the changes: remove work_item_id column and make agent_id required again

-- First, restore the work_items table with required agent_id
CREATE TABLE v2_work_items_old (
    work_item_id TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL
                   REFERENCES v2_user(user_id)  ON DELETE CASCADE,
    agent_id     TEXT NOT NULL
                   REFERENCES v2_agent(agent_id) ON DELETE CASCADE,
    thread_id    TEXT
                   REFERENCES v2_thread(thread_id) ON DELETE SET NULL,

    status            TEXT NOT NULL,
    created_at        TEXT NOT NULL
                          DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    updated_at        TEXT NOT NULL
                          DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    completed_by      TEXT,
    status_updated_at TEXT NOT NULL
                          DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    status_updated_by TEXT NOT NULL DEFAULT 'SYSTEM',

    messages TEXT NOT NULL,   -- JSON serialised
    payload  TEXT NOT NULL    -- JSON serialised
);

-- Copy data from current table to old table (only rows with non-null agent_id)
INSERT INTO v2_work_items_old 
SELECT * FROM v2_work_items WHERE agent_id IS NOT NULL;

-- Drop current table
DROP TABLE v2_work_items;

-- Rename old table to original name
ALTER TABLE v2_work_items_old RENAME TO v2_work_items;

-- Recreate indexes
CREATE INDEX IF NOT EXISTS idx_work_items_status          ON v2_work_items(status);
CREATE INDEX IF NOT EXISTS idx_work_items_created_at      ON v2_work_items(created_at);
CREATE INDEX IF NOT EXISTS idx_work_items_status_created  ON v2_work_items(status, created_at)
                                                          WHERE status = 'PENDING';

-- Now restore the file_owner table without work_item_id column
CREATE TABLE v2_file_owner_old
(
    file_id TEXT PRIMARY KEY,
    file_ref TEXT,
    file_path TEXT,
    file_hash TEXT,
    file_size_raw INTEGER,
    mime_type TEXT,
    user_id TEXT,
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
    CONSTRAINT fk_file_owner_user_id
      FOREIGN KEY (user_id)
      REFERENCES v2_user(user_id)
      ON DELETE CASCADE,
    CONSTRAINT unique_file_ref_thread
      UNIQUE (file_ref, thread_id)
);

-- Copy data from the current table to the old table, excluding work_item_id
INSERT INTO v2_file_owner_old(file_id, file_ref, file_path, file_hash, file_size_raw, mime_type, user_id, embedded, agent_id, thread_id, file_path_expiration, created_at)
    SELECT file_id, file_ref, file_path, file_hash, file_size_raw, mime_type, user_id, embedded, agent_id, thread_id, file_path_expiration, created_at
    FROM v2_file_owner WHERE work_item_id IS NULL;

-- Drop the current table
DROP TABLE v2_file_owner;

-- Rename the old table to the original name
ALTER TABLE v2_file_owner_old RENAME TO v2_file_owner;

-- Create indexes for lookups
CREATE INDEX idx_file_owner_agent_id ON v2_file_owner(agent_id);
CREATE INDEX idx_file_owner_thread_id ON v2_file_owner(thread_id);
CREATE INDEX idx_file_owner_user_id ON v2_file_owner(user_id);