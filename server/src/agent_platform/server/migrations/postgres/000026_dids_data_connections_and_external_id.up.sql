-- Document Intelligence Data Server data connections
CREATE TABLE IF NOT EXISTS v2."dids_data_connections" (
    external_id TEXT,
    name TEXT NOT NULL,
    engine TEXT NOT NULL,
    configuration JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Add external_id field to document_intelligence_integrations table
ALTER TABLE v2."document_intelligence_integrations" 
ADD COLUMN external_id TEXT NOT NULL DEFAULT '';
