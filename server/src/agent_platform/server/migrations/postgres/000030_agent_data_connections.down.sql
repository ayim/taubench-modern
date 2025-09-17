-- Drop indexes
DROP INDEX IF EXISTS v2.idx_agent_data_connections_data_connection_id;
DROP INDEX IF EXISTS v2.idx_agent_data_connections_agent_id;
-- Drop the agent_data_connections table
DROP TABLE IF EXISTS v2."agent_data_connections";