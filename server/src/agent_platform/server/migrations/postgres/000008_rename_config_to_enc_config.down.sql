-- Revert config column name back to config
ALTER TABLE v2.mcp_server RENAME COLUMN enc_config TO config; 