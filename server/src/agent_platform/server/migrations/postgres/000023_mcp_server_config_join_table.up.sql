CREATE TABLE IF NOT EXISTS v2."agent_mcp_server" (
  agent_id      UUID NOT NULL,
  mcp_server_id UUID NOT NULL,
  PRIMARY KEY (agent_id, mcp_server_id),
  CONSTRAINT v2_agent_mcp_server_agent_fk
    FOREIGN KEY (agent_id)
    REFERENCES v2.agent(agent_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT v2_agent_mcp_server_mcp_fk
    FOREIGN KEY (mcp_server_id)
    REFERENCES v2.mcp_server(mcp_server_id)
    ON DELETE CASCADE ON UPDATE CASCADE
);
