-- Revert column type from TEXT back to JSONB and rename from enc_parameters back to parameters
ALTER TABLE v2.platform_params ALTER COLUMN enc_parameters TYPE JSONB USING enc_parameters::JSONB;
ALTER TABLE v2.platform_params RENAME COLUMN enc_parameters TO parameters;