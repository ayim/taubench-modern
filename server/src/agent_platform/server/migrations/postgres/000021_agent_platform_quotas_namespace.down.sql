-- Drop the unique constraint on (config_type, namespace)
ALTER TABLE v2."agent_config" DROP CONSTRAINT IF EXISTS agent_config_config_type_namespace_key;

-- Add back the original unique constraint on config_type
ALTER TABLE v2."agent_config" ADD CONSTRAINT agent_config_config_type_key UNIQUE (config_type);

-- Drop the namespace column
ALTER TABLE v2."agent_config" DROP COLUMN namespace;
