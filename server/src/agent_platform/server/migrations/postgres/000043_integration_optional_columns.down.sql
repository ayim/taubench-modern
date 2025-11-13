ALTER TABLE v2.integration DROP COLUMN IF EXISTS version;
ALTER TABLE v2.integration DROP COLUMN IF EXISTS description;
ALTER TABLE v2.integration ADD CONSTRAINT integration_kind_key UNIQUE (kind);

