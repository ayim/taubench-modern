-- Drop unified integrations table
DROP TABLE IF EXISTS v2_integration;
-- Drop tags column from data connection table
ALTER TABLE
  v2_data_connection DROP COLUMN tags;