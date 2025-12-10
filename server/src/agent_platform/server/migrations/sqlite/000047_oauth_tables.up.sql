-- OAuth Token table
CREATE TABLE v2_oauth_token (
    user_id TEXT NOT NULL,
    mcp_url TEXT NOT NULL,
    access_token_enc TEXT NOT NULL,
    token_type TEXT NOT NULL DEFAULT 'Bearer',
    expires_in INTEGER,
    scope TEXT,
    refresh_token_enc TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    expires_at TEXT NOT NULL,
    
    PRIMARY KEY (user_id, mcp_url),
    
    CONSTRAINT fk_oauth_token_user_id
      FOREIGN KEY (user_id)
      REFERENCES v2_user(user_id)
      ON DELETE CASCADE
);

CREATE INDEX idx_oauth_token_user_mcp ON v2_oauth_token(user_id, mcp_url);

-- OAuth Client Information table
CREATE TABLE v2_oauth_client_info (
    user_id TEXT NOT NULL,
    mcp_url TEXT NOT NULL,
    client_id_enc TEXT NOT NULL,
    client_secret_enc TEXT,
    client_id_issued_at INTEGER,
    client_secret_expires_at INTEGER,
    metadata_json TEXT NOT NULL CHECK (json_valid(metadata_json)),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    expires_at TEXT,
    
    PRIMARY KEY (user_id, mcp_url),
    
    CONSTRAINT fk_oauth_client_info_user_id
      FOREIGN KEY (user_id)
      REFERENCES v2_user(user_id)
      ON DELETE CASCADE
);

CREATE INDEX idx_oauth_client_info_user_mcp ON v2_oauth_client_info(user_id, mcp_url);

-- OAuth Callback Result table
CREATE TABLE v2_oauth_callback_result (
    callback_id TEXT PRIMARY KEY,
    code TEXT,
    state TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

