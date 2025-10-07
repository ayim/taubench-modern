-- Add tags column to data connection table
ALTER TABLE
  v2."data_connection"
ADD
  COLUMN tags JSONB DEFAULT '[]' :: jsonb;
-- Create unified integrations table
  CREATE TABLE IF NOT EXISTS v2."integration" (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    kind TEXT NOT NULL UNIQUE,
    enc_settings JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
  );