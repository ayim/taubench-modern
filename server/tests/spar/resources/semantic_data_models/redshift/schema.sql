-- E-commerce Test Schema for Semantic Data Models (Redshift)
-- This file creates the table structure and relationships
-- Note: Redshift doesn't support SERIAL, TIMESTAMP defaults, or all PostgreSQL features

-- Customers table
CREATE TABLE customers (
  id INTEGER NOT NULL,
  name VARCHAR(100) NOT NULL,
  email VARCHAR(100) NOT NULL,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  PRIMARY KEY (id)
);

-- Products table
CREATE TABLE products (
  id INTEGER NOT NULL,
  name VARCHAR(200) NOT NULL,
  description VARCHAR(MAX),
  price DECIMAL(10, 2) NOT NULL,
  category VARCHAR(50),
  stock_quantity INTEGER NOT NULL DEFAULT 0,
  created_at TIMESTAMP,
  updated_at TIMESTAMP,
  PRIMARY KEY (id)
);

-- Orders table
CREATE TABLE orders (
  id INTEGER NOT NULL,
  customer_id INTEGER NOT NULL,
  order_date TIMESTAMP,
  status VARCHAR(20) NOT NULL,
  total_amount DECIMAL(10, 2) NOT NULL,
  shipping_address VARCHAR(MAX),
  notes VARCHAR(MAX),
  PRIMARY KEY (id),
  FOREIGN KEY (customer_id) REFERENCES customers(id)
);

-- Order items table (junction table with additional data)
CREATE TABLE order_items (
  id INTEGER NOT NULL,
  order_id INTEGER NOT NULL,
  product_id INTEGER NOT NULL,
  quantity INTEGER NOT NULL,
  unit_price DECIMAL(10, 2) NOT NULL,
  PRIMARY KEY (id),
  FOREIGN KEY (order_id) REFERENCES orders(id),
  FOREIGN KEY (product_id) REFERENCES products(id)
);

-- Invoice Comparison table for testing comprehensive SDM column types
-- This table tests facts (numeric), time_dimensions (timestamp), and dimensions (text)
CREATE TABLE comparison_v1_v2 (
  document_name VARCHAR(500) NOT NULL,
  v1_invoice_total NUMERIC,
  v1_line_items_total NUMERIC,
  v1_line_items_count INTEGER,
  v2_invoice_total NUMERIC,
  v2_line_items_total NUMERIC,
  v2_line_items_count INTEGER,
  created_at TIMESTAMPTZ NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL,
  export_status VARCHAR(50) NOT NULL DEFAULT 'INIT',
  PRIMARY KEY (document_name)
);

-- Create indexes for common query patterns
-- Note: Redshift uses different index syntax (compound sort keys, dist keys)
-- For test purposes, we'll keep basic indexes but they work differently in Redshift
-- In production, you would use SORTKEY and DISTKEY

