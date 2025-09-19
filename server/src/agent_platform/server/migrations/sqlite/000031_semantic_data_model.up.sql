-- Semantic Data Model table
CREATE TABLE IF NOT EXISTS v2_semantic_data_model (
  id TEXT PRIMARY KEY,
  semantic_model TEXT NOT NULL CHECK (json_valid(semantic_model)),
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);
-- Junction table for semantic data model and data connections
CREATE TABLE IF NOT EXISTS v2_semantic_data_model_input_data_connections (
  semantic_data_model_id TEXT NOT NULL,
  data_connection_id TEXT NOT NULL,
  PRIMARY KEY (semantic_data_model_id, data_connection_id),
  CONSTRAINT fk_semantic_data_model_input_data_connections_semantic_data_model_id FOREIGN KEY (semantic_data_model_id) REFERENCES v2_semantic_data_model (id) ON DELETE CASCADE,
  CONSTRAINT fk_semantic_data_model_input_data_connections_data_connection_id FOREIGN KEY (data_connection_id) REFERENCES v2_data_connection (id) ON DELETE CASCADE
);
-- Junction table for semantic data model and file references
CREATE TABLE IF NOT EXISTS v2_semantic_data_model_input_file_references (
  semantic_data_model_id TEXT NOT NULL,
  thread_id TEXT NOT NULL,
  file_ref TEXT NOT NULL,
  PRIMARY KEY (semantic_data_model_id, thread_id, file_ref),
  CONSTRAINT fk_semantic_data_model_input_file_references_semantic_data_model_id FOREIGN KEY (semantic_data_model_id) REFERENCES v2_semantic_data_model (id) ON DELETE CASCADE,
  CONSTRAINT fk_semantic_data_model_input_file_references_file FOREIGN KEY (thread_id, file_ref) REFERENCES v2_file_owner (thread_id, file_ref) ON DELETE CASCADE
);
-- Indexes for efficient lookups
CREATE INDEX IF NOT EXISTS idx_semantic_data_model_input_data_connections_semantic_data_model_id ON v2_semantic_data_model_input_data_connections (semantic_data_model_id);
CREATE INDEX IF NOT EXISTS idx_semantic_data_model_input_data_connections_data_connection_id ON v2_semantic_data_model_input_data_connections (data_connection_id);
CREATE INDEX IF NOT EXISTS idx_semantic_data_model_input_file_references_semantic_data_model_id ON v2_semantic_data_model_input_file_references (semantic_data_model_id);
CREATE INDEX IF NOT EXISTS idx_semantic_data_model_input_file_references_thread_id_file_ref ON v2_semantic_data_model_input_file_references (thread_id, file_ref);