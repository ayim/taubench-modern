-- Add tags column to data connection table
ALTER TABLE
  v2_data_connection
ADD
  COLUMN tags TEXT DEFAULT '[]' CHECK (json_valid(tags));
-- Create unified integrations table
  CREATE TABLE IF NOT EXISTS v2_integration (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL UNIQUE,
    enc_settings TEXT NOT NULL CHECK (json_valid(enc_settings)),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
  );