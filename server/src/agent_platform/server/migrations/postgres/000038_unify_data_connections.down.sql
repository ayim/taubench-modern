-- Drop unified integrations table
DROP TABLE IF EXISTS v2."integration";
-- Drop tags column from data connection table
ALTER TABLE
  v2."data_connection" DROP COLUMN tags;