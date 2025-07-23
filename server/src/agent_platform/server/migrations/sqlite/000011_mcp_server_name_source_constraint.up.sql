-- Drop the old unique index on name only
DROP INDEX IF EXISTS idx_mcp_server_name;
-- Create new unique index on name + source combination
CREATE UNIQUE INDEX idx_mcp_server_name_source ON v2_mcp_server(name, source);