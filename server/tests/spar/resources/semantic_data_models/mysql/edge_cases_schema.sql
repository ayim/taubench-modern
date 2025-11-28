-- Edge Cases Test Schema for MySQL Semantic Data Models
-- This file contains tables with special MySQL data types and edge cases
-- Compatible with MySQL 8.0+
-- Products with JSON metadata (MySQL 5.7.8+)
CREATE TABLE products_with_json (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(200) NOT NULL,
  -- JSON column for flexible metadata
  metadata JSON COMMENT 'Flexible JSON metadata for product attributes',
  -- JSON column for specifications
  specifications JSON COMMENT 'Product specifications in JSON format',
  -- Array stored as JSON
  tags JSON COMMENT 'Product tags stored as JSON array',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE = InnoDB COMMENT = 'Products with JSON metadata for flexible attributes';
-- User preferences with JSON configuration
CREATE TABLE user_preferences (
  id INT AUTO_INCREMENT PRIMARY KEY,
  user_id INT NOT NULL,
  -- JSON for nested configuration objects
  preferences JSON NOT NULL COMMENT 'User preferences with nested structure',
  -- JSON for audit history
  change_history JSON COMMENT 'History of preference changes',
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE = InnoDB COMMENT = 'User preferences stored as JSON for complex configurations';
-- Events log with JSON payload
CREATE TABLE event_logs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  event_type VARCHAR(50) NOT NULL,
  -- JSON payload for event data
  payload JSON NOT NULL COMMENT 'JSON payload containing event details',
  -- JSON for indexed metadata
  metadata JSON COMMENT 'Additional metadata about the event',
  occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE = InnoDB COMMENT = 'Event logs with JSON payloads for audit trails';
-- Geo locations with JSON for coordinates
CREATE TABLE locations (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(200) NOT NULL,
  -- JSON for coordinates
  coordinates JSON COMMENT 'Coordinates stored as JSON object {lat, lon}',
  -- JSON for detailed address
  address JSON COMMENT 'Detailed address information in JSON',
  -- Spatial point type
  location_point POINT COMMENT 'Geographic point location',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE = InnoDB COMMENT = 'Geographic locations with JSON and spatial data';
-- Products with advanced MySQL types
CREATE TABLE advanced_products (
  id INT AUTO_INCREMENT PRIMARY KEY,
  sku VARCHAR(36) NOT NULL,
  name VARCHAR(200) NOT NULL,
  -- JSON for complex pricing structures
  pricing_rules JSON COMMENT 'Complex pricing rules in JSON format',
  -- ENUM for categories
  category ENUM(
    'electronics',
    'furniture',
    'kitchen',
    'office',
    'outdoor'
  ) DEFAULT 'electronics',
  -- SET for multiple tags
  product_tags
  SET(
      'new',
      'sale',
      'featured',
      'bestseller',
      'clearance'
    ),
    -- JSON for inventory tracking
    inventory_details JSON COMMENT 'Inventory tracking details',
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE = InnoDB COMMENT = 'Products with advanced MySQL types';
-- Table with all MySQL temporal types
CREATE TABLE temporal_data_test (
  id INT AUTO_INCREMENT PRIMARY KEY,
  -- Date only
  date_only DATE COMMENT 'Date without time',
  -- DateTime with microseconds
  datetime_precise DATETIME(6) COMMENT 'DateTime with microsecond precision',
  -- Timestamp with automatic update
  created_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  -- Time only
  time_only TIME COMMENT 'Time without date',
  -- Time with microseconds
  time_precise TIME(6) COMMENT 'Time with microsecond precision',
  -- Year
  year_only YEAR COMMENT 'Year only (YYYY)'
) ENGINE = InnoDB COMMENT = 'Table testing all MySQL temporal/date-time types';
-- Table with all MySQL numeric types including edge cases
CREATE TABLE numeric_edge_cases (
  id BIGINT AUTO_INCREMENT PRIMARY KEY,
  -- Signed integers at boundaries
  tiny_min TINYINT COMMENT 'Minimum TINYINT value',
  tiny_max TINYINT COMMENT 'Maximum TINYINT value',
  small_min SMALLINT COMMENT 'Minimum SMALLINT value',
  small_max SMALLINT COMMENT 'Maximum SMALLINT value',
  medium_min MEDIUMINT COMMENT 'Minimum MEDIUMINT value',
  medium_max MEDIUMINT COMMENT 'Maximum MEDIUMINT value',
  int_min INT COMMENT 'Minimum INT value',
  int_max INT COMMENT 'Maximum INT value',
  bigint_min BIGINT COMMENT 'Minimum BIGINT value',
  bigint_max BIGINT COMMENT 'Maximum BIGINT value',
  -- Unsigned integers
  tiny_unsigned TINYINT UNSIGNED COMMENT 'Unsigned TINYINT (0-255)',
  small_unsigned SMALLINT UNSIGNED COMMENT 'Unsigned SMALLINT',
  int_unsigned INT UNSIGNED COMMENT 'Unsigned INT',
  bigint_unsigned BIGINT UNSIGNED COMMENT 'Unsigned BIGINT',
  -- Floating point edge cases
  float_zero FLOAT COMMENT 'Zero value',
  float_negative FLOAT COMMENT 'Negative float',
  float_small FLOAT COMMENT 'Very small float',
  float_large FLOAT COMMENT 'Very large float',
  double_precision DOUBLE COMMENT 'Double precision value',
  -- Decimal precision tests
  decimal_precise DECIMAL(65, 30) COMMENT 'Maximum precision decimal',
  decimal_money DECIMAL(19, 4) COMMENT 'Money with 4 decimal places',
  -- Zero values
  zero_int INT DEFAULT 0,
  zero_decimal DECIMAL(10, 2) DEFAULT 0.00
) ENGINE = InnoDB COMMENT = 'Table testing numeric edge cases and boundary values';
-- Table with all MySQL string/text types
CREATE TABLE string_edge_cases (
  id INT AUTO_INCREMENT PRIMARY KEY,
  -- Fixed and variable length strings
  char_fixed CHAR(255) COMMENT 'Fixed length CHAR (max 255)',
  varchar_long VARCHAR(2000) COMMENT 'Long VARCHAR',
  -- Text types of various sizes
  tiny_text TINYTEXT COMMENT 'TINYTEXT (255 bytes)',
  regular_text TEXT COMMENT 'TEXT (65,535 bytes)',
  medium_text MEDIUMTEXT COMMENT 'MEDIUMTEXT (16MB)',
  long_text LONGTEXT COMMENT 'LONGTEXT (4GB)',
  -- Special characters and encoding
  utf8_content VARCHAR(500) CHARACTER SET utf8mb4 COMMENT 'UTF-8 content with emojis',
  -- Empty and NULL handling
  nullable_text TEXT COMMENT 'Can be NULL',
  empty_varchar VARCHAR(100) DEFAULT '' COMMENT 'Empty string default'
) ENGINE = InnoDB COMMENT = 'Table testing all string and text types with edge cases';
-- Table with binary data types
CREATE TABLE binary_edge_cases (
  id INT AUTO_INCREMENT PRIMARY KEY,
  -- Fixed and variable binary
  binary_fixed BINARY(16) COMMENT 'Fixed length binary (16 bytes)',
  varbinary_data VARBINARY(255) COMMENT 'Variable length binary',
  -- BLOB types
  tiny_blob TINYBLOB COMMENT 'TINYBLOB (255 bytes)',
  regular_blob BLOB COMMENT 'BLOB (65KB)',
  medium_blob MEDIUMBLOB COMMENT 'MEDIUMBLOB (16MB)',
  long_blob LONGBLOB COMMENT 'LONGBLOB (4GB)'
) ENGINE = InnoDB COMMENT = 'Table testing binary data types';
-- Table with ENUM and SET edge cases
CREATE TABLE enum_set_edge_cases (
  id INT AUTO_INCREMENT PRIMARY KEY,
  -- ENUM with many values
  size_enum ENUM(
    'xxs',
    'xs',
    'small',
    'medium',
    'large',
    'xl',
    'xxl',
    '3xl',
    '4xl',
    '5xl'
  ) COMMENT 'Size enumeration',
  -- ENUM with special characters
  status_enum ENUM(
    'draft',
    'in-progress',
    'pending-review',
    'approved',
    'rejected',
    'archived'
  ) COMMENT 'Status with hyphens',
  -- SET with multiple values
  permissions
  SET(
      'read',
      'write',
      'delete',
      'admin',
      'superuser',
      'audit',
      'export',
      'import'
    ) COMMENT 'Permission flags',
    -- SET with all values selected
    features
  SET(
      'feature_a',
      'feature_b',
      'feature_c',
      'feature_d'
    ) COMMENT 'Feature flags',
    -- NULL handling
    nullable_enum ENUM('yes', 'no', 'maybe') COMMENT 'Nullable enum',
    nullable_set
  SET('option1', 'option2', 'option3') COMMENT 'Nullable set'
) ENGINE = InnoDB COMMENT = 'Table testing ENUM and SET types with edge cases';
-- Table with spatial data types (MySQL 8.0+)
CREATE TABLE spatial_edge_cases (
  id INT AUTO_INCREMENT PRIMARY KEY,
  -- Basic geometry types (NOT NULL required for spatial indexes)
  point_location POINT NOT NULL COMMENT 'Point geometry',
  line_route LINESTRING COMMENT 'Line string geometry',
  poly_area POLYGON NOT NULL COMMENT 'Polygon geometry',
  -- Multi-part geometries
  multi_point MULTIPOINT COMMENT 'Multiple points',
  multi_line MULTILINESTRING COMMENT 'Multiple line strings',
  multi_poly MULTIPOLYGON COMMENT 'Multiple polygons',
  -- Generic geometry
  generic_geom GEOMETRY COMMENT 'Generic geometry type',
  -- Geometry collection
  geom_collection GEOMETRYCOLLECTION COMMENT 'Collection of geometries'
) ENGINE = InnoDB COMMENT = 'Table testing MySQL spatial/geometry types';
-- Table with JSON array and object variations
CREATE TABLE json_complex_structures (
  id INT AUTO_INCREMENT PRIMARY KEY,
  -- Simple JSON values
  json_null JSON COMMENT 'JSON null value',
  json_bool JSON COMMENT 'JSON boolean',
  json_number JSON COMMENT 'JSON number',
  json_string JSON COMMENT 'JSON string',
  -- Arrays
  json_array_empty JSON COMMENT 'Empty JSON array',
  json_array_numbers JSON COMMENT 'Array of numbers',
  json_array_strings JSON COMMENT 'Array of strings',
  json_array_mixed JSON COMMENT 'Mixed type array',
  json_array_nested JSON COMMENT 'Nested arrays',
  -- Objects
  json_object_empty JSON COMMENT 'Empty JSON object',
  json_object_simple JSON COMMENT 'Simple key-value object',
  json_object_nested JSON COMMENT 'Deeply nested object',
  json_object_arrays JSON COMMENT 'Object containing arrays',
  -- Complex structures
  json_complex JSON COMMENT 'Complex mixed structure',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE = InnoDB COMMENT = 'Table testing complex JSON structures';
-- Create indexes for better query performance
CREATE INDEX idx_products_json_name ON products_with_json(name);
CREATE INDEX idx_user_prefs_user_id ON user_preferences(user_id);
CREATE INDEX idx_event_logs_type ON event_logs(event_type);
CREATE INDEX idx_event_logs_occurred ON event_logs(occurred_at);
CREATE INDEX idx_locations_name ON locations(name);
CREATE INDEX idx_advanced_products_sku ON advanced_products(sku);
CREATE INDEX idx_advanced_products_category ON advanced_products(category);
CREATE INDEX idx_temporal_date ON temporal_data_test(date_only);
CREATE INDEX idx_temporal_datetime ON temporal_data_test(datetime_precise);
CREATE INDEX idx_numeric_int ON numeric_edge_cases(int_min, int_max);
CREATE INDEX idx_string_varchar ON string_edge_cases(varchar_long(255));
-- Spatial index for geometry columns
CREATE SPATIAL INDEX idx_spatial_point ON spatial_edge_cases(point_location);
CREATE SPATIAL INDEX idx_spatial_poly ON spatial_edge_cases(poly_area);