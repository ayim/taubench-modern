CREATE TABLE v2_data_frames (
  -- Primary key
  data_frame_id TEXT PRIMARY KEY,
  -- UUID as string
  -- Required fields
  user_id TEXT NOT NULL REFERENCES v2_user(user_id) ON DELETE CASCADE,
  agent_id TEXT NOT NULL REFERENCES v2_agent(agent_id) ON DELETE CASCADE,
  thread_id TEXT NOT NULL REFERENCES v2_thread(thread_id) ON DELETE CASCADE,
  num_rows INTEGER NOT NULL,
  num_columns INTEGER NOT NULL,
  column_headers JSON NOT NULL,
  name TEXT NOT NULL,
  input_id_type TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  computation_input_sources JSON,
  sheet_name TEXT NULL,
  file_id TEXT NULL REFERENCES v2_file_owner(file_id) ON DELETE
  SET
    NULL,
    description TEXT NULL,
    computation TEXT NULL,
    -- SQL computation string
    parquet_contents BLOB NULL, -- Binary data for parquet contents
    extra_data JSON NULL
);
CREATE INDEX IF NOT EXISTS idx_data_frames_thread_id ON v2_data_frames(thread_id);