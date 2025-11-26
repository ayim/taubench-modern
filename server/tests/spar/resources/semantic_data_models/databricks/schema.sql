-- E-commerce Test Schema for Semantic Data Models (Databricks)
--
-- Note: Using lowercase identifiers for test compatibility
-- Databricks limitations: No foreign key enforcement, limited constraint support
-- Using IDENTITY columns for auto-increment behavior
-- Customers table
CREATE TABLE customers (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name STRING NOT NULL,
  email STRING NOT NULL,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
) COMMENT 'Customer information and contact details';
-- Products table
CREATE TABLE products (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  name STRING NOT NULL,
  description STRING,
  price DECIMAL(10, 2) NOT NULL,
  category STRING,
  stock_quantity INT NOT NULL,
  created_at TIMESTAMP,
  updated_at TIMESTAMP
) COMMENT 'Product catalog with pricing and inventory';
-- Orders table (customer_id references customers.id)
CREATE TABLE orders (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  customer_id BIGINT NOT NULL,
  order_date TIMESTAMP,
  status STRING NOT NULL,
  total_amount DECIMAL(10, 2) NOT NULL,
  shipping_address STRING,
  notes STRING
) COMMENT 'Customer orders with status and totals. customer_id references customers.id';
-- Order items table (order_id references orders.id, product_id references products.id)
CREATE TABLE order_items (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  order_id BIGINT NOT NULL,
  product_id BIGINT NOT NULL,
  quantity INT NOT NULL,
  unit_price DECIMAL(10, 2) NOT NULL
) COMMENT 'Individual line items within each order. order_id references orders.id, product_id references products.id';
-- Invoice Comparison table for testing comprehensive SDM column types
-- This table tests facts (numeric), time_dimensions (timestamp), and dimensions (text)
CREATE TABLE comparison_v1_v2 (
  document_name STRING NOT NULL,
  v1_invoice_total DECIMAL(18, 2),
  v1_line_items_total DECIMAL(18, 2),
  v1_line_items_count INT,
  v2_invoice_total DECIMAL(18, 2),
  v2_line_items_total DECIMAL(18, 2),
  v2_line_items_count INT,
  created_at TIMESTAMP NOT NULL,
  updated_at TIMESTAMP NOT NULL,
  export_status STRING NOT NULL,
  PRIMARY KEY (document_name)
) COMMENT 'Invoice comparison data between version 1 and version 2 processing';
-- Enable column defaults feature and add default values for timestamp columns
ALTER TABLE
  customers
SET
  TBLPROPERTIES(
    'delta.feature.allowColumnDefaults' = 'supported'
  );
ALTER TABLE
  customers
ALTER COLUMN
  created_at
SET
  DEFAULT CURRENT_TIMESTAMP();
ALTER TABLE
  customers
ALTER COLUMN
  updated_at
SET
  DEFAULT CURRENT_TIMESTAMP();
ALTER TABLE
  products
SET
  TBLPROPERTIES(
    'delta.feature.allowColumnDefaults' = 'supported'
  );
ALTER TABLE
  products
ALTER COLUMN
  created_at
SET
  DEFAULT CURRENT_TIMESTAMP();
ALTER TABLE
  products
ALTER COLUMN
  updated_at
SET
  DEFAULT CURRENT_TIMESTAMP();
ALTER TABLE
  products
ALTER COLUMN
  stock_quantity
SET
  DEFAULT 0;
ALTER TABLE
  orders
SET
  TBLPROPERTIES(
    'delta.feature.allowColumnDefaults' = 'supported'
  );
ALTER TABLE
  orders
ALTER COLUMN
  order_date
SET
  DEFAULT CURRENT_TIMESTAMP();