-- Add namespace column with default 'global'
ALTER TABLE v2."agent_config" ADD COLUMN namespace TEXT NOT NULL DEFAULT 'global';

-- Drop existing unique constraint on config_type
ALTER TABLE v2."agent_config" DROP CONSTRAINT IF EXISTS agent_config_config_type_key;

-- Add new unique constraint on (config_type, namespace)
ALTER TABLE v2."agent_config" ADD CONSTRAINT agent_config_config_type_namespace_key UNIQUE (config_type, namespace);
