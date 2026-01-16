-- Composite Foreign Key Test Schema for PostgreSQL
-- Minimal schema to test composite FK detection
-- Parent table with composite PK (2 columns)
CREATE TABLE regions (
  country_code VARCHAR(2) NOT NULL,
  region_code VARCHAR(10) NOT NULL,
  region_name VARCHAR(100) NOT NULL,
  PRIMARY KEY (country_code, region_code)
);
-- Child table with composite FK referencing regions
CREATE TABLE stores (
  id SERIAL PRIMARY KEY,
  store_name VARCHAR(100) NOT NULL,
  country_code VARCHAR(2) NOT NULL,
  region_code VARCHAR(10) NOT NULL,
  CONSTRAINT fk_stores_region FOREIGN KEY (country_code, region_code) REFERENCES regions(country_code, region_code)
);