-- Enum type for MCP server source
CREATE TYPE v2.mcp_server_source AS ENUM ('FILE', 'API');
CREATE TABLE v2.mcp_server (
    mcp_server_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    config JSONB NOT NULL,
    source v2.mcp_server_source NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
);
CREATE UNIQUE INDEX idx_mcp_server_name ON v2.mcp_server(name);