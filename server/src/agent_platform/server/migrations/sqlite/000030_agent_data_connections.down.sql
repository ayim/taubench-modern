-- Drop indexes
DROP INDEX IF EXISTS idx_agent_data_connections_data_connection_id;
DROP INDEX IF EXISTS idx_agent_data_connections_agent_id;
-- Drop the agent_data_connections table
DROP TABLE IF EXISTS v2_agent_data_connections;