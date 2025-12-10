-- OAuth Token table
CREATE TABLE v2."oauth_token" (
    user_id UUID NOT NULL,
    mcp_url TEXT NOT NULL,
    access_token_enc TEXT NOT NULL,
    token_type TEXT NOT NULL DEFAULT 'Bearer',
    expires_in INTEGER,
    scope TEXT,
    refresh_token_enc TEXT,
    created_at TIMESTAMP WITH TIME ZONE 
               DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    updated_at TIMESTAMP WITH TIME ZONE 
               DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    
    PRIMARY KEY (user_id, mcp_url),
    
    CONSTRAINT fk_oauth_token_user_id
      FOREIGN KEY (user_id)
      REFERENCES v2."user"(user_id)
      ON DELETE CASCADE
);

CREATE INDEX idx_oauth_token_user_mcp ON v2."oauth_token"(user_id, mcp_url);

-- OAuth Client Information table
CREATE TABLE v2."oauth_client_info" (
    user_id UUID NOT NULL,
    mcp_url TEXT NOT NULL,
    client_id_enc TEXT NOT NULL,
    client_secret_enc TEXT,
    client_id_issued_at INTEGER,
    client_secret_expires_at INTEGER,
    metadata_json JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE 
               DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    updated_at TIMESTAMP WITH TIME ZONE 
               DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    expires_at TIMESTAMP WITH TIME ZONE,

    PRIMARY KEY (user_id, mcp_url),
    
    CONSTRAINT fk_oauth_client_info_user_id
      FOREIGN KEY (user_id)
      REFERENCES v2."user"(user_id)
      ON DELETE CASCADE
);

CREATE INDEX idx_oauth_client_info_user_mcp ON v2."oauth_client_info"(user_id, mcp_url);

-- OAuth Callback Result table
CREATE TABLE v2."oauth_callback_result" (
    callback_id TEXT PRIMARY KEY,
    code TEXT,
    state TEXT,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE 
               DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
);

