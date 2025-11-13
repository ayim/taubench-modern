CREATE TABLE v2_integration_new (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL, -- No unique constraint, as we support multiple observability integrations
    enc_settings TEXT NOT NULL CHECK (json_valid(enc_settings)),
    description TEXT,
    version TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

INSERT INTO
  v2_integration_new (
    id,
    kind,
    enc_settings,
    description,
    version,
    created_at,
    updated_at
  )
SELECT
  id,
  kind,
  enc_settings,
  NULL,
  NULL,
  created_at,
  updated_at
FROM
  v2_integration;

DROP TABLE v2_integration;

ALTER TABLE v2_integration_new RENAME TO v2_integration;