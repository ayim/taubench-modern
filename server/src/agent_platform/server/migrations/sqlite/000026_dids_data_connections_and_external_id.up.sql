-- Document Intelligence Data Server data connections
CREATE TABLE IF NOT EXISTS v2_dids_data_connections (
    external_id TEXT,
    name TEXT NOT NULL,
    engine TEXT NOT NULL,
    configuration TEXT NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Add external_id field to document_intelligence_integrations table
ALTER TABLE v2_document_intelligence_integrations 
ADD COLUMN external_id TEXT NOT NULL DEFAULT '';
