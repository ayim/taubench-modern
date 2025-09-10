CREATE TABLE v2_agent_platform_params (
  agent_id      TEXT NOT NULL,
  platform_params_id TEXT NOT NULL,
  PRIMARY KEY (agent_id, platform_params_id),
  FOREIGN KEY (agent_id)      REFERENCES v2_agent(agent_id)            ON DELETE CASCADE ON UPDATE CASCADE,
  FOREIGN KEY (platform_params_id) REFERENCES v2_platform_params(platform_params_id)  ON DELETE CASCADE ON UPDATE CASCADE
);