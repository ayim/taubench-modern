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
    status VARCHAR(20) NOT NULL CHECK (status IN ('pending', 'processing', 'completed', 'cancelled')),
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

