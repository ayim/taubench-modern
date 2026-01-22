-- Test schema that reproduces BIRD database scenario
-- Where foreign keys reference UNIQUE INDEX instead of PRIMARY KEY
-- This causes information_schema.referential_constraints.unique_constraint_name to be NULL
-- But pg_catalog.pg_constraint still has complete FK metadata
-- Parent table with UNIQUE INDEX (not PRIMARY KEY or UNIQUE CONSTRAINT)
CREATE TABLE territories (
  country_code VARCHAR(2) NOT NULL,
  territory_code VARCHAR(10) NOT NULL,
  territory_name VARCHAR(100) NOT NULL
);
-- Create UNIQUE INDEX instead of PRIMARY KEY
-- This mimics SQLite-to-PostgreSQL transpilation by sqlglot
CREATE UNIQUE INDEX idx_territories_unique ON territories(country_code, territory_code);
-- Child table referencing the UNIQUE INDEX
CREATE TABLE outlets (
  id SERIAL PRIMARY KEY,
  outlet_name VARCHAR(100) NOT NULL,
  country_code VARCHAR(2) NOT NULL,
  territory_code VARCHAR(10) NOT NULL,
  -- FK references columns with UNIQUE INDEX (not PK)
  CONSTRAINT fk_outlets_territory FOREIGN KEY (country_code, territory_code) REFERENCES territories(country_code, territory_code)
);