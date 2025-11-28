-- E-commerce Test Schema for MySQL Semantic Data Models
-- This file creates the table structure and relationships
-- Compatible with MySQL 8.0+
-- Customers table
CREATE TABLE customers (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  email VARCHAR(100) UNIQUE NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE = InnoDB COMMENT = 'Customer information and contact details';
-- Products table
CREATE TABLE products (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(200) NOT NULL,
  description TEXT,
  price DECIMAL(10, 2) NOT NULL CHECK (price >= 0),
  category VARCHAR(50),
  stock_quantity INT NOT NULL DEFAULT 0 CHECK (stock_quantity >= 0),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE = InnoDB COMMENT = 'Product catalog with pricing and inventory';
-- Orders table
CREATE TABLE orders (
  id INT AUTO_INCREMENT PRIMARY KEY,
  customer_id INT NOT NULL,
  order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  status VARCHAR(20) NOT NULL CHECK (
    status IN (
      'pending',
      'processing',
      'completed',
      'cancelled'
    )
  ),
  total_amount DECIMAL(10, 2) NOT NULL CHECK (total_amount >= 0),
  shipping_address TEXT,
  notes TEXT,
  FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE CASCADE
) ENGINE = InnoDB COMMENT = 'Customer orders with status and totals';
-- Order items table (junction table with additional data)
CREATE TABLE order_items (
  id INT AUTO_INCREMENT PRIMARY KEY,
  order_id INT NOT NULL,
  product_id INT NOT NULL,
  quantity INT NOT NULL CHECK (quantity > 0),
  unit_price DECIMAL(10, 2) NOT NULL CHECK (unit_price >= 0),
  UNIQUE KEY unique_order_product (order_id, product_id),
  FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
  FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
) ENGINE = InnoDB COMMENT = 'Individual line items within each order';
-- Create indexes for common query patterns
CREATE INDEX idx_orders_customer_id ON orders(customer_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_order_date ON orders(order_date);
CREATE INDEX idx_order_items_order_id ON order_items(order_id);
CREATE INDEX idx_order_items_product_id ON order_items(product_id);
CREATE INDEX idx_products_category ON products(category);
-- Invoice Comparison table for testing comprehensive SDM column types
CREATE TABLE comparison_v1_v2 (
  document_name VARCHAR(255) NOT NULL PRIMARY KEY,
  v1_invoice_total DECIMAL(15, 2),
  v1_line_items_total DECIMAL(15, 2),
  v1_line_items_count INT,
  v2_invoice_total DECIMAL(15, 2),
  v2_line_items_total DECIMAL(15, 2),
  v2_line_items_count INT,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  export_status VARCHAR(50) NOT NULL DEFAULT 'INIT'
) ENGINE = InnoDB COMMENT = 'Invoice comparison data between version 1 and version 2 processing';
CREATE INDEX idx_comparison_export_status ON comparison_v1_v2(export_status);
CREATE INDEX idx_comparison_created_at ON comparison_v1_v2(created_at);
CREATE INDEX idx_comparison_updated_at ON comparison_v1_v2(updated_at);
-- Comprehensive MySQL Data Types Test Table
-- This table covers all major MySQL data types for thorough testing
CREATE TABLE mysql_data_types_test (
  -- Primary Key
  id BIGINT AUTO_INCREMENT PRIMARY KEY COMMENT 'Auto-incrementing primary key',
  -- Numeric Types
  tinyint_col TINYINT COMMENT 'Very small integer (-128 to 127)',
  smallint_col SMALLINT COMMENT 'Small integer (-32768 to 32767)',
  mediumint_col MEDIUMINT COMMENT 'Medium integer (-8388608 to 8388607)',
  int_col INT COMMENT 'Standard integer',
  bigint_col BIGINT COMMENT 'Large integer',
  decimal_col DECIMAL(10, 2) COMMENT 'Fixed-point decimal (10 digits, 2 decimal places)',
  numeric_col NUMERIC(8, 3) COMMENT 'Alias for DECIMAL',
  float_col FLOAT COMMENT 'Single-precision floating point',
  double_col DOUBLE COMMENT 'Double-precision floating point',
  -- Boolean (stored as TINYINT(1))
  bool_col BOOLEAN COMMENT 'Boolean value (TRUE/FALSE)',
  -- String Types
  char_col CHAR(10) COMMENT 'Fixed-length string (10 characters)',
  varchar_col VARCHAR(255) COMMENT 'Variable-length string (up to 255 characters)',
  tinytext_col TINYTEXT COMMENT 'Tiny text (up to 255 characters)',
  text_col TEXT COMMENT 'Text (up to 65,535 characters)',
  mediumtext_col MEDIUMTEXT COMMENT 'Medium text (up to 16,777,215 characters)',
  longtext_col LONGTEXT COMMENT 'Long text (up to 4,294,967,295 characters)',
  -- Binary Types
  binary_col BINARY(16) COMMENT 'Fixed-length binary (16 bytes)',
  varbinary_col VARBINARY(255) COMMENT 'Variable-length binary',
  tinyblob_col TINYBLOB COMMENT 'Tiny blob (up to 255 bytes)',
  blob_col BLOB COMMENT 'Blob (up to 65,535 bytes)',
  mediumblob_col MEDIUMBLOB COMMENT 'Medium blob',
  longblob_col LONGBLOB COMMENT 'Long blob',
  -- Date and Time Types
  date_col DATE COMMENT 'Date (YYYY-MM-DD)',
  datetime_col DATETIME COMMENT 'Date and time (YYYY-MM-DD HH:MM:SS)',
  timestamp_col TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Timestamp (auto-updates)',
  time_col TIME COMMENT 'Time (HH:MM:SS)',
  year_col YEAR COMMENT 'Year (YYYY)',
  -- JSON Type (MySQL 5.7.8+)
  json_col JSON COMMENT 'JSON document',
  -- Enum and Set
  enum_col ENUM('small', 'medium', 'large', 'x-large') COMMENT 'Enumeration type',
  set_col
  SET('red', 'green', 'blue', 'yellow') COMMENT 'Set type (multiple values)',
    -- Spatial Types (basic examples)
    point_col POINT COMMENT 'Geometric point',
    linestring_col LINESTRING COMMENT 'Line string',
    polygon_col POLYGON COMMENT 'Polygon',
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT 'Record creation timestamp',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT 'Record update timestamp'
) ENGINE = InnoDB COMMENT = 'Comprehensive test table covering all major MySQL data types';
-- Index for testing query patterns
CREATE INDEX idx_mysql_test_int_col ON mysql_data_types_test(int_col);
CREATE INDEX idx_mysql_test_varchar_col ON mysql_data_types_test(varchar_col);
CREATE INDEX idx_mysql_test_date_col ON mysql_data_types_test(date_col);
CREATE INDEX idx_mysql_test_enum_col ON mysql_data_types_test(enum_col);
-- Invoice documents table with JSON columns for testing complex JSON operations
CREATE TABLE invoice_documents (
  document_id VARCHAR(255) PRIMARY KEY,
  document_title TEXT,
  document_layout TEXT,
  model_type VARCHAR(100) NOT NULL,
  content_extracted JSON COMMENT 'JSON structure: {customer: object, line_items: array of {description, amount, volume, price}, invoice_total: number, invoice_number: string, invoice_date: string}',
  content_translated JSON COMMENT 'JSON structure: {Buyer: object, Transactions: array, Invoice_details: {invoice_total, invoice_number, invoice_date}}',
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE = InnoDB COMMENT = 'Invoice documents with nested JSON for testing array aggregation and nested field extraction';
CREATE INDEX idx_invoice_documents_model_type ON invoice_documents(model_type);
CREATE INDEX idx_invoice_documents_created_at ON invoice_documents(created_at);