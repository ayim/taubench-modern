-- Drop indexes
DROP INDEX IF EXISTS v2.idx_mcp_server_source;
DROP INDEX IF EXISTS v2.idx_mcp_server_name;
DROP INDEX IF EXISTS v2.idx_mcp_server_user_id;

-- Drop the table
DROP TABLE IF EXISTS v2.mcp_server;

-- Drop the enum type at last 
DROP TYPE IF EXISTS v2.mcp_server_source;
