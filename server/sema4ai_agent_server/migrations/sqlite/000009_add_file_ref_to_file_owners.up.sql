-- First, add the file_ref column if it doesn't exist
ALTER TABLE file_owners ADD COLUMN file_ref TEXT;

-- Update file_ref with file_path
UPDATE file_owners SET file_ref = file_path;

-- Add file_path_expiration column if it doesn't exist
ALTER TABLE file_owners ADD COLUMN file_path_expiration DATETIME;

-- Create a temporary table with the desired structure
CREATE TABLE file_owners_temp (
    file_id TEXT NOT NULL,
    file_ref TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    embedded BOOLEAN NOT NULL,
    assistant_id TEXT,
    thread_id TEXT,
    file_path_expiration DATETIME,
    PRIMARY KEY (file_id),
    FOREIGN KEY (assistant_id) REFERENCES assistant(assistant_id) ON DELETE SET NULL,
    FOREIGN KEY (thread_id) REFERENCES thread(thread_id) ON DELETE SET NULL,
    CONSTRAINT unique_file_ref_assistant UNIQUE (file_ref, assistant_id),
    CONSTRAINT unique_file_ref_thread UNIQUE (file_ref, thread_id)
);

-- Copy data from the old table to the new one
INSERT INTO file_owners_temp (
    file_id,
    file_ref,
    file_path,
    file_hash,
    embedded,
    assistant_id,
    thread_id,
    file_path_expiration
)
SELECT
    file_id,
    file_ref,
    file_path,
    file_hash,
    embedded,
    assistant_id,
    thread_id,
    file_path_expiration
FROM file_owners;

-- Drop the old table
DROP TABLE file_owners;

-- Rename the new table to the original name
ALTER TABLE file_owners_temp RENAME TO file_owners;