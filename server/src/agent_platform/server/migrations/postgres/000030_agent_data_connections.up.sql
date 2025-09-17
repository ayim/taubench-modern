-- Agent Data Connections junction table
CREATE TABLE IF NOT EXISTS v2."agent_data_connections" (
  agent_id UUID NOT NULL,
  data_connection_id UUID NOT NULL,
  PRIMARY KEY (agent_id, data_connection_id),
  CONSTRAINT fk_agent_data_connections_agent_id FOREIGN KEY (agent_id) REFERENCES v2."agent" (agent_id) ON DELETE CASCADE,
  CONSTRAINT fk_agent_data_connections_data_connection_id FOREIGN KEY (data_connection_id) REFERENCES v2."data_connection" (id) ON DELETE CASCADE
);
-- Index for efficient lookups by agent_id
CREATE INDEX IF NOT EXISTS idx_agent_data_connections_agent_id ON v2."agent_data_connections" (agent_id);
-- Index for efficient lookups by data_connection_id
CREATE INDEX IF NOT EXISTS idx_agent_data_connections_data_connection_id ON v2."agent_data_connections" (data_connection_id);