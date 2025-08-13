CREATE TABLE v2."data_frames" (
  -- Primary key
  data_frame_id UUID PRIMARY KEY,
  -- UUID as string
  -- Required fields
  user_id UUID NOT NULL REFERENCES v2.user(user_id) ON DELETE CASCADE,
  agent_id UUID NOT NULL REFERENCES v2.agent(agent_id) ON DELETE CASCADE,
  thread_id UUID NOT NULL REFERENCES v2.thread(thread_id) ON DELETE CASCADE,
  num_rows INTEGER NOT NULL,
  num_columns INTEGER NOT NULL,
  column_headers JSONB NOT NULL,
  name TEXT NOT NULL,
  input_id_type TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
  computation_input_sources JSONB,
  sheet_name TEXT NULL,
  file_id TEXT NULL REFERENCES v2.file_owner(file_id) ON DELETE
  SET
    NULL,
    description TEXT NULL,
    computation TEXT NULL,
    -- SQL computation string
    parquet_contents BYTEA NULL, -- Binary data for parquet contents
    extra_data JSONB NULL
);
CREATE INDEX IF NOT EXISTS idx_data_frames_thread_id ON v2.data_frames(thread_id);