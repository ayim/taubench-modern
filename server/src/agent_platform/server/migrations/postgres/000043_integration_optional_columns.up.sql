ALTER TABLE v2.integration ADD COLUMN description TEXT;
ALTER TABLE v2.integration ADD COLUMN version TEXT;
-- Drop the unique constraint on the kind column, as we support multiple observability integrations
ALTER TABLE v2.integration DROP CONSTRAINT IF EXISTS integration_kind_key;
