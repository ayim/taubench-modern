BEGIN TRANSACTION;

CREATE TABLE IF NOT EXISTS data_models (
    name                 TEXT PRIMARY KEY NOT NULL,
    description              TEXT,
    model_schema           TEXT,
    prompt                   TEXT, -- optional prompt field
    created_timestamp        TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_timestamp        TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS document_layouts (
    name              TEXT PRIMARY KEY,
    data_model                 TEXT NOT NULL, -- reference to data_models.name
    extraction_schema        TEXT,
    translation_schema       TEXT,
    created_timestamp        TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_timestamp        TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
);

CREATE TABLE IF NOT EXISTS documents (
    document_id              UUID PRIMARY KEY NOT NULL,
    document_name            TEXT,
    layout_name              TEXT, -- reference to document_layouts.name
    data_model                 TEXT NOT NULL, -- reference to data_models.name
    extracted_output         TEXT, -- SQLite have JSON type
    translated_output       TEXT, -- SQLite have JSON type
    created_timestamp        TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_timestamp        TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
);

COMMIT;
