PRAGMA foreign_keys = ON;

CREATE TABLE v2_agent_mcp_server (
  agent_id      TEXT NOT NULL,
  mcp_server_id TEXT NOT NULL,
  PRIMARY KEY (agent_id, mcp_server_id),
  FOREIGN KEY (agent_id)      REFERENCES v2_agent(agent_id)            ON DELETE CASCADE ON UPDATE CASCADE,
  FOREIGN KEY (mcp_server_id) REFERENCES v2_mcp_server(mcp_server_id)  ON DELETE CASCADE ON UPDATE CASCADE
);
