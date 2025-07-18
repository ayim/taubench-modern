-- MCP server table
CREATE TABLE v2_mcp_server (
    mcp_server_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    config TEXT NOT NULL CHECK (json_valid(config)),
    source TEXT NOT NULL CHECK (source IN ('FILE', 'API')),
    created_at TEXT DEFAULT (datetime('now', 'utc')),
    updated_at TEXT DEFAULT (datetime('now', 'utc'))
);
CREATE UNIQUE INDEX idx_mcp_server_name ON v2_mcp_server(name);