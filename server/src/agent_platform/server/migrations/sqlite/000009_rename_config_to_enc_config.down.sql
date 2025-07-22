-- Revert enc_config column name back to config
ALTER TABLE v2_mcp_server RENAME COLUMN enc_config TO config; 