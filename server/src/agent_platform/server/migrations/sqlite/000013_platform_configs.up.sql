CREATE TABLE v2_platform_params (
    platform_params_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    parameters TEXT NOT NULL CHECK (json_valid(parameters)), -- Store the entire PlatformParameters object
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- Ensure platform config names are unique
CREATE UNIQUE INDEX idx_platform_params_name ON v2_platform_params(name);