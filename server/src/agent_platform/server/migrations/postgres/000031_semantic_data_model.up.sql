-- Semantic Data Model table
CREATE TABLE IF NOT EXISTS v2."semantic_data_model" (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  semantic_model JSONB NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
);
-- Junction table for semantic data model and data connections
CREATE TABLE IF NOT EXISTS v2."semantic_data_model_input_data_connections" (
  semantic_data_model_id UUID NOT NULL,
  data_connection_id UUID NOT NULL,
  PRIMARY KEY (semantic_data_model_id, data_connection_id),
  CONSTRAINT fk_semantic_data_model_input_data_connections_semantic_data_model_id FOREIGN KEY (semantic_data_model_id) REFERENCES v2."semantic_data_model" (id) ON DELETE CASCADE,
  CONSTRAINT fk_semantic_data_model_input_data_connections_data_connection_id FOREIGN KEY (data_connection_id) REFERENCES v2."data_connection" (id) ON DELETE CASCADE
);
-- Junction table for semantic data model and file references
CREATE TABLE IF NOT EXISTS v2."semantic_data_model_input_file_references" (
  semantic_data_model_id UUID NOT NULL,
  thread_id UUID NOT NULL,
  file_ref TEXT NOT NULL,
  PRIMARY KEY (semantic_data_model_id, thread_id, file_ref),
  CONSTRAINT fk_semantic_data_model_input_file_references_semantic_data_model_id FOREIGN KEY (semantic_data_model_id) REFERENCES v2."semantic_data_model" (id) ON DELETE CASCADE,
  CONSTRAINT fk_semantic_data_model_input_file_references_file FOREIGN KEY (thread_id, file_ref) REFERENCES v2."file_owner" (thread_id, file_ref) ON DELETE CASCADE
);
-- Indexes for efficient lookups
CREATE INDEX IF NOT EXISTS idx_semantic_data_model_input_data_connections_semantic_data_model_id ON v2."semantic_data_model_input_data_connections" (semantic_data_model_id);
CREATE INDEX IF NOT EXISTS idx_semantic_data_model_input_data_connections_data_connection_id ON v2."semantic_data_model_input_data_connections" (data_connection_id);
CREATE INDEX IF NOT EXISTS idx_semantic_data_model_input_file_references_semantic_data_model_id ON v2."semantic_data_model_input_file_references" (semantic_data_model_id);
CREATE INDEX IF NOT EXISTS idx_semantic_data_model_input_file_references_thread_id_file_ref ON v2."semantic_data_model_input_file_references" (thread_id, file_ref);