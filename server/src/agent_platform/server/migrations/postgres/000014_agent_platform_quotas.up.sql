CREATE TABLE IF NOT EXISTS v2."agent_config" (
    id UUID PRIMARY KEY NOT NULL DEFAULT uuid_generate_v4(),
    config_type TEXT NOT NULL UNIQUE,
    config_value JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
