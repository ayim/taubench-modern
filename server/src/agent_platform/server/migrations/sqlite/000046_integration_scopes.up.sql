-- Create integration_scopes junction table for scoped observability configuration
-- Supports additive scoping: agents receive global configs + agent-specific configs
CREATE TABLE v2_integration_scopes (
    integration_id TEXT NOT NULL REFERENCES v2_integration(id) ON DELETE CASCADE,
    agent_id TEXT NULL REFERENCES v2_agent(agent_id) ON DELETE CASCADE,
    scope TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
    
    -- No PRIMARY KEY because agent_id can be NULL (SQL doesn't allow NULL in PK)
    -- Uniqueness is enforced by partial indexes below
);

-- Partial unique index to prevent duplicate global scopes for same integration
-- Ensures only one (integration_id, 'global') row can exist
CREATE UNIQUE INDEX unique_integration_global ON v2_integration_scopes(integration_id) 
WHERE scope = 'global';

-- Partial unique index to prevent duplicate agent scopes for same integration-agent pair
-- Ensures only one (integration_id, 'agent') row per agent
CREATE UNIQUE INDEX unique_integration_agent ON v2_integration_scopes(integration_id, agent_id) 
WHERE scope = 'agent';
