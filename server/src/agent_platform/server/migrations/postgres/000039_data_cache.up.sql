-- Data cache table
CREATE TABLE IF NOT EXISTS v2."data_cache" (
  cache_key TEXT PRIMARY KEY,
  cache_data BYTEA NOT NULL,
  last_accessed_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
  time_to_compute_data_in_seconds FLOAT NOT NULL,
  cache_size_in_bytes INTEGER NOT NULL
);

-- Index for efficient LRU cache eviction
CREATE INDEX IF NOT EXISTS idx_data_cache_last_accessed_at ON v2."data_cache" (last_accessed_at);
