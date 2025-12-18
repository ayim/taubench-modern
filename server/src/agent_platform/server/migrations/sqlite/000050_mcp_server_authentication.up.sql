-- Add authentication_type and authentication_metadata_enc columns to mcp_server table
ALTER TABLE v2_mcp_server ADD COLUMN authentication_type TEXT DEFAULT NULL;
ALTER TABLE v2_mcp_server ADD COLUMN authentication_metadata_enc TEXT DEFAULT NULL;

