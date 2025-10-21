-- Data cache table
CREATE TABLE IF NOT EXISTS v2_data_cache (
  cache_key TEXT PRIMARY KEY,
  cache_data BLOB NOT NULL,
  last_accessed_at TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  time_to_compute_data_in_seconds REAL NOT NULL,
  cache_size_in_bytes INTEGER NOT NULL
);

-- Index for efficient LRU cache eviction
CREATE INDEX IF NOT EXISTS idx_data_cache_last_accessed_at ON v2_data_cache (last_accessed_at);
