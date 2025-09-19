-- Drop indexes
DROP INDEX IF EXISTS idx_semantic_data_model_input_file_references_thread_id_file_ref;
DROP INDEX IF EXISTS idx_semantic_data_model_input_file_references_semantic_data_model_id;
DROP INDEX IF EXISTS idx_semantic_data_model_input_data_connections_data_connection_id;
DROP INDEX IF EXISTS idx_semantic_data_model_input_data_connections_semantic_data_model_id;
-- Drop junction tables
DROP TABLE IF EXISTS v2."semantic_data_model_input_file_references";
DROP TABLE IF EXISTS v2."semantic_data_model_input_data_connections";
-- Drop main table
DROP TABLE IF EXISTS v2."semantic_data_model";