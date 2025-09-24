-- Agent Semantic Data Models junction table
CREATE TABLE IF NOT EXISTS v2."agent_semantic_data_models" (
  agent_id UUID NOT NULL,
  semantic_data_model_id UUID NOT NULL,
  PRIMARY KEY (agent_id, semantic_data_model_id),
  CONSTRAINT fk_agent_semantic_data_models_agent_id FOREIGN KEY (agent_id) REFERENCES v2."agent" (agent_id) ON DELETE CASCADE,
  CONSTRAINT fk_agent_semantic_data_models_semantic_data_model_id FOREIGN KEY (semantic_data_model_id) REFERENCES v2."semantic_data_model" (id) ON DELETE CASCADE
);
-- Index for efficient lookups by agent_id
CREATE INDEX IF NOT EXISTS idx_agent_semantic_data_models_agent_id ON v2."agent_semantic_data_models" (agent_id);
-- Index for efficient lookups by semantic_data_model_id
CREATE INDEX IF NOT EXISTS idx_agent_semantic_data_models_semantic_data_model_id ON v2."agent_semantic_data_models" (semantic_data_model_id);
-- Thread Semantic Data Models junction table
CREATE TABLE IF NOT EXISTS v2."thread_semantic_data_models" (
  thread_id UUID NOT NULL,
  semantic_data_model_id UUID NOT NULL,
  PRIMARY KEY (thread_id, semantic_data_model_id),
  CONSTRAINT fk_thread_semantic_data_models_thread_id FOREIGN KEY (thread_id) REFERENCES v2."thread" (thread_id) ON DELETE CASCADE,
  CONSTRAINT fk_thread_semantic_data_models_semantic_data_model_id FOREIGN KEY (semantic_data_model_id) REFERENCES v2."semantic_data_model" (id) ON DELETE CASCADE
);
-- Index for efficient lookups by thread_id
CREATE INDEX IF NOT EXISTS idx_thread_semantic_data_models_thread_id ON v2."thread_semantic_data_models" (thread_id);
-- Index for efficient lookups by semantic_data_model_id
CREATE INDEX IF NOT EXISTS idx_thread_semantic_data_models_semantic_data_model_id ON v2."thread_semantic_data_models" (semantic_data_model_id);