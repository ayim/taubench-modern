CREATE TABLE IF NOT EXISTS v2_data_connection (
  id TEXT PRIMARY KEY,
  external_id TEXT,
  name TEXT NOT NULL,
  description TEXT NOT NULL,
  enc_configuration TEXT NOT NULL CHECK (json_valid(enc_configuration)),
  engine TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);