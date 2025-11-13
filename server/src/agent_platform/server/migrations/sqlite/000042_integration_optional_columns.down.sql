CREATE TABLE v2_integration_old (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL UNIQUE,
    enc_settings TEXT NOT NULL CHECK (json_valid(enc_settings)),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
  );

INSERT INTO
  v2_integration_old (id, kind, enc_settings, created_at, updated_at)
SELECT
  id,
  kind,
  enc_settings,
  created_at,
  updated_at
FROM
  v2_integration;

DROP TABLE v2_integration;

ALTER TABLE v2_integration_old RENAME TO v2_integration;