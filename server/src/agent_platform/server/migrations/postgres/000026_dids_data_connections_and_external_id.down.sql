-- Drop Document Intelligence Data Server data connections table
DROP TABLE IF EXISTS v2."dids_data_connections";

-- Remove external_id field from document_intelligence_integrations table
ALTER TABLE v2."document_intelligence_integrations" 
DROP COLUMN external_id;
