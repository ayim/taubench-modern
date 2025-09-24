-- Drop indexes
DROP INDEX IF EXISTS v2.idx_thread_semantic_data_models_semantic_data_model_id;
DROP INDEX IF EXISTS v2.idx_thread_semantic_data_models_thread_id;
DROP INDEX IF EXISTS v2.idx_agent_semantic_data_models_semantic_data_model_id;
DROP INDEX IF EXISTS v2.idx_agent_semantic_data_models_agent_id;
-- Drop the junction tables
DROP TABLE IF EXISTS v2."thread_semantic_data_models";
DROP TABLE IF EXISTS v2."agent_semantic_data_models";