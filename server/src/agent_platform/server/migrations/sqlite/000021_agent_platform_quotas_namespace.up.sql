-- Add namespace column with default 'global'
ALTER TABLE v2_agent_config ADD COLUMN namespace TEXT NOT NULL DEFAULT 'global';

-- Drop existing unique constraint on config_type
CREATE TABLE v2_agent_config_temp (
    id TEXT PRIMARY KEY NOT NULL,
    config_type TEXT NOT NULL,
    config_value TEXT NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    namespace TEXT NOT NULL DEFAULT 'global'
);

INSERT INTO v2_agent_config_temp SELECT * FROM v2_agent_config;
DROP TABLE v2_agent_config;
ALTER TABLE v2_agent_config_temp RENAME TO v2_agent_config;

-- Add new unique constraint on (config_type, namespace)
CREATE UNIQUE INDEX v2_agent_config_type_namespace_idx ON v2_agent_config (config_type, namespace);
