-- Remove authentication_type and authentication_metadata_enc columns from mcp_server table
ALTER TABLE v2_mcp_server DROP COLUMN IF EXISTS authentication_metadata_enc;
ALTER TABLE v2_mcp_server DROP COLUMN IF EXISTS authentication_type;

