CREATE TABLE IF NOT EXISTS v2."agent_platform_params" (
  agent_id      UUID NOT NULL,
  platform_params_id UUID NOT NULL,
  PRIMARY KEY (agent_id, platform_params_id),
  CONSTRAINT v2_agent_platform_params_agent_fk
    FOREIGN KEY (agent_id)
    REFERENCES v2.agent(agent_id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT v2_agent_platform_params_platform_params_fk
    FOREIGN KEY (platform_params_id)
    REFERENCES v2.platform_params(platform_params_id)
    ON DELETE CASCADE ON UPDATE CASCADE
);
