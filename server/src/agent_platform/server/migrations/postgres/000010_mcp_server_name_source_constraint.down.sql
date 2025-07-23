-- Drop the name + source unique index
DROP INDEX IF EXISTS v2.idx_mcp_server_name_source;
-- Recreate the old unique index on name only
CREATE UNIQUE INDEX idx_mcp_server_name ON v2.mcp_server(name);