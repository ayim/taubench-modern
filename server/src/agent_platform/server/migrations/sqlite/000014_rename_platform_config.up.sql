-- Rename parameters column to enc_parameters to establish naming convention for encrypted columns
ALTER TABLE v2_platform_params RENAME COLUMN parameters TO enc_parameters;