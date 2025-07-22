-- Rename config column to enc_config to establish naming convention for encrypted columns
ALTER TABLE v2.mcp_server RENAME COLUMN config TO enc_config; 