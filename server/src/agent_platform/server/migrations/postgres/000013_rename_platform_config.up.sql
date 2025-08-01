-- Rename parameters column to enc_parameters and change type from JSONB to TEXT for encrypted data storage
ALTER TABLE v2.platform_params RENAME COLUMN parameters TO enc_parameters;
ALTER TABLE v2.platform_params ALTER COLUMN enc_parameters TYPE TEXT;