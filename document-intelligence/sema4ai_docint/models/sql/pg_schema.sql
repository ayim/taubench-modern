BEGIN;
CREATE TABLE IF NOT EXISTS data_models (
    name                 TEXT PRIMARY KEY NOT NULL,
    description              TEXT,
    model_schema           JSONB,
    views                    JSONB, -- map of view_name to view_definition
    quality_checks         JSONB, -- map of view name to list of validation rules
    prompt                   TEXT, -- optional prompt field
    base_config     JSONB,
    summary                  TEXT,
    created_at        TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at        TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS document_layouts (
    name                  TEXT NOT NULL,
    data_model            TEXT NOT NULL, -- reference to data_models.name
    extraction_schema     JSONB,
    translation_schema    JSONB,
    summary               TEXT,
    extraction_config     JSONB,
    system_prompt         TEXT,
    created_at            TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at            TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    PRIMARY KEY (name, data_model)
);

CREATE TABLE IF NOT EXISTS documents (
    id                       TEXT PRIMARY KEY NOT NULL,
    document_name            TEXT,
    document_layout              TEXT, -- reference to document_layouts.name
    data_model                 TEXT NOT NULL, -- reference to data_models.name
    extracted_content        JSONB,
    translated_content      JSON,
    created_at        TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at        TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE OR REPLACE FUNCTION try_to_number(p_text text)
RETURNS numeric
LANGUAGE sql
IMMUTABLE
STRICT
PARALLEL SAFE
AS $$
SELECT CASE
    WHEN btrim($1) ~ '^[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?$'
    THEN replace(btrim($1), ',', '')::numeric
    ELSE NULL::numeric
END
$$;

COMMIT;
