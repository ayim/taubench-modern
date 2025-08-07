-- Document Intelligence Data Server connection details
CREATE TABLE IF NOT EXISTS v2_dids_connection_details (
    username TEXT NOT NULL,
    enc_password TEXT NOT NULL,
    connections TEXT NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Document Intelligence integrations
CREATE TABLE IF NOT EXISTS v2_document_intelligence_integrations (
    kind TEXT PRIMARY KEY,
    endpoint TEXT NOT NULL,
    enc_api_key TEXT NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);