-- Drop the unique constraint on (config_type, namespace) and add back the original constraint on config_type
CREATE TABLE v2_agent_config_temp (
    id TEXT PRIMARY KEY NOT NULL,
    config_type TEXT NOT NULL UNIQUE,
    config_value TEXT NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO v2_agent_config_temp SELECT id, config_type, config_value, updated_at FROM v2_agent_config;
DROP TABLE v2_agent_config;
ALTER TABLE v2_agent_config_temp RENAME TO v2_agent_config;
