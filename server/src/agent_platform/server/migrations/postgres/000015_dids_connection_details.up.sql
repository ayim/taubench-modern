-- Document Intelligence Data Server connection details
CREATE TABLE IF NOT EXISTS v2."dids_connection_details" (
    username TEXT NOT NULL,
    enc_password TEXT NOT NULL,
    connections JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Document Intelligence integrations
CREATE TABLE IF NOT EXISTS v2."document_intelligence_integrations" (
    kind TEXT PRIMARY KEY,
    endpoint TEXT NOT NULL,
    enc_api_key TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);