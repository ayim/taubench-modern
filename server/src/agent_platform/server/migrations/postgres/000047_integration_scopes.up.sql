-- Create integration_scopes junction table for scoped observability configuration
-- Supports additive scoping: agents receive global configs + agent-specific configs
CREATE TABLE v2.integration_scopes (
    integration_id UUID NOT NULL REFERENCES v2.integration(id) ON DELETE CASCADE,
    agent_id UUID NULL REFERENCES v2.agent(agent_id) ON DELETE CASCADE,
    scope TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
    
    -- No PRIMARY KEY because agent_id can be NULL (PostgreSQL doesn't allow NULL in PK)
    -- Uniqueness is enforced by partial indexes below
);

-- Partial unique index to prevent duplicate global scopes for same integration
-- Ensures only one (integration_id, 'global') row can exist
CREATE UNIQUE INDEX unique_integration_global ON v2.integration_scopes(integration_id) 
WHERE scope = 'global';

-- Partial unique index to prevent duplicate agent scopes for same integration-agent pair
-- Ensures only one (integration_id, 'agent') row per agent
CREATE UNIQUE INDEX unique_integration_agent ON v2.integration_scopes(integration_id, agent_id) 
WHERE scope = 'agent';
