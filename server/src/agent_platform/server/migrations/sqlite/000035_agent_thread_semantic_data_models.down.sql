-- Drop indexes
DROP INDEX IF EXISTS idx_thread_semantic_data_models_semantic_data_model_id;
DROP INDEX IF EXISTS idx_thread_semantic_data_models_thread_id;
DROP INDEX IF EXISTS idx_agent_semantic_data_models_semantic_data_model_id;
DROP INDEX IF EXISTS idx_agent_semantic_data_models_agent_id;
-- Drop the junction tables
DROP TABLE IF EXISTS v2_thread_semantic_data_models;
DROP TABLE IF EXISTS v2_agent_semantic_data_models;