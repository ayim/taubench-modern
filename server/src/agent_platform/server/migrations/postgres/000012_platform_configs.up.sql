CREATE TABLE v2.platform_params (
    platform_params_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    parameters JSONB NOT NULL, -- Store the entire PlatformParameters object
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
);

-- Ensure platform config names are unique per user
CREATE UNIQUE INDEX idx_platform_params_name ON v2.platform_params(name);