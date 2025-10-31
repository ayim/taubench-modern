-- E-commerce Test Schema for Semantic Data Models
-- This file creates the table structure and relationships
-- Customers table
CREATE TABLE customers (
  id SERIAL PRIMARY KEY,
  name VARCHAR(100) NOT NULL,
  email VARCHAR(100) UNIQUE NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- Products table
CREATE TABLE products (
  id SERIAL PRIMARY KEY,
  name VARCHAR(200) NOT NULL,
  description TEXT,
  price DECIMAL(10, 2) NOT NULL CHECK (price >= 0),
  category VARCHAR(50),
  stock_quantity INTEGER NOT NULL DEFAULT 0 CHECK (stock_quantity >= 0),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- Orders table
CREATE TABLE orders (
  id SERIAL PRIMARY KEY,
  customer_id INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
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
  notes TEXT
);
-- Order items table (junction table with additional data)
CREATE TABLE order_items (
  id SERIAL PRIMARY KEY,
  order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE RESTRICT,
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  unit_price DECIMAL(10, 2) NOT NULL CHECK (unit_price >= 0),
  -- Composite unique constraint to prevent duplicate items in same order
  UNIQUE (order_id, product_id)
);
-- Create indexes for common query patterns
CREATE INDEX idx_orders_customer_id ON orders(customer_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_order_date ON orders(order_date);
CREATE INDEX idx_order_items_order_id ON order_items(order_id);
CREATE INDEX idx_order_items_product_id ON order_items(product_id);
CREATE INDEX idx_products_category ON products(category);
-- Comments for documentation (useful for semantic model generation)
COMMENT ON TABLE customers IS 'Customer information and contact details';
COMMENT ON TABLE products IS 'Product catalog with pricing and inventory';
COMMENT ON TABLE orders IS 'Customer orders with status and totals';
COMMENT ON TABLE order_items IS 'Individual line items within each order';
COMMENT ON COLUMN customers.email IS 'Customer email address, must be unique';
COMMENT ON COLUMN products.price IS 'Current price per unit in USD';
COMMENT ON COLUMN products.stock_quantity IS 'Number of units available in inventory';
COMMENT ON COLUMN orders.status IS 'Order processing status: pending, processing, completed, or cancelled';
COMMENT ON COLUMN orders.total_amount IS 'Total order amount including all items';
COMMENT ON COLUMN order_items.quantity IS 'Number of units of this product in the order';
COMMENT ON COLUMN order_items.unit_price IS 'Price per unit at time of order (may differ from current product price)';
-- Invoice Comparison table for testing comprehensive SDM column types
-- This table tests facts (numeric), time_dimensions (timestamp), and dimensions (text)
CREATE TABLE comparison_v1_v2 (
  document_name TEXT NOT NULL,
  v1_invoice_total NUMERIC,
  v1_line_items_total NUMERIC,
  v1_line_items_count INTEGER,
  v2_invoice_total NUMERIC,
  v2_line_items_total NUMERIC,
  v2_line_items_count INTEGER,
  created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
  export_status TEXT NOT NULL DEFAULT 'INIT',
  PRIMARY KEY (document_name)
);
-- Create indexes for common query patterns
CREATE INDEX idx_comparison_export_status ON comparison_v1_v2(export_status);
CREATE INDEX idx_comparison_created_at ON comparison_v1_v2(created_at);
CREATE INDEX idx_comparison_updated_at ON comparison_v1_v2(updated_at);
-- Comments for documentation
COMMENT ON TABLE comparison_v1_v2 IS 'Invoice comparison data between version 1 and version 2 processing';
COMMENT ON COLUMN comparison_v1_v2.document_name IS 'Unique name of the document being compared';
COMMENT ON COLUMN comparison_v1_v2.v1_invoice_total IS 'Total invoice amount from version 1 processing';
COMMENT ON COLUMN comparison_v1_v2.v1_line_items_total IS 'Sum of line items from version 1 processing';
COMMENT ON COLUMN comparison_v1_v2.v1_line_items_count IS 'Count of line items from version 1 processing';
COMMENT ON COLUMN comparison_v1_v2.v2_invoice_total IS 'Total invoice amount from version 2 processing';
COMMENT ON COLUMN comparison_v1_v2.v2_line_items_total IS 'Sum of line items from version 2 processing';
COMMENT ON COLUMN comparison_v1_v2.v2_line_items_count IS 'Count of line items from version 2 processing';
COMMENT ON COLUMN comparison_v1_v2.created_at IS 'Timestamp when the comparison record was first created';
COMMENT ON COLUMN comparison_v1_v2.updated_at IS 'Timestamp when the comparison record was last updated';
COMMENT ON COLUMN comparison_v1_v2.export_status IS 'Export status of the comparison: INIT, EXPORTED, or other values';