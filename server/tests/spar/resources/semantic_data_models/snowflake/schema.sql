-- E-commerce Test Schema for Semantic Data Models (Snowflake)
--
-- Note: All identifiers are quoted to preserve lowercase names (Snowflake converts unquoted to UPPERCASE)
-- Snowflake limitations: No CHECK constraints, no indexes on regular tables, foreign keys informational only
-- Customers table
CREATE TABLE "customers" (
  "id" INTEGER AUTOINCREMENT PRIMARY KEY,
  "name" VARCHAR(100) NOT NULL,
  "email" VARCHAR(100) UNIQUE NOT NULL,
  "created_at" TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
  "updated_at" TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
-- Products table
CREATE TABLE "products" (
  "id" INTEGER AUTOINCREMENT PRIMARY KEY,
  "name" VARCHAR(200) NOT NULL,
  "description" VARCHAR(5000),
  "price" NUMBER(10, 2) NOT NULL,
  "category" VARCHAR(50),
  "stock_quantity" INTEGER NOT NULL DEFAULT 0,
  "created_at" TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
  "updated_at" TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
-- Orders table (customer_id references customers.id)
CREATE TABLE "orders" (
  "id" INTEGER AUTOINCREMENT PRIMARY KEY,
  "customer_id" INTEGER NOT NULL,
  "order_date" TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
  "status" VARCHAR(20) NOT NULL,
  "total_amount" NUMBER(10, 2) NOT NULL,
  "shipping_address" VARCHAR(5000),
  "notes" VARCHAR(5000)
);
-- Order items table (order_id references orders.id, product_id references products.id)
CREATE TABLE "order_items" (
  "id" INTEGER AUTOINCREMENT PRIMARY KEY,
  "order_id" INTEGER NOT NULL,
  "product_id" INTEGER NOT NULL,
  "quantity" INTEGER NOT NULL,
  "unit_price" NUMBER(10, 2) NOT NULL,
  UNIQUE ("order_id", "product_id")
);
-- Comments for documentation
COMMENT ON TABLE "customers" IS 'Customer information and contact details';
COMMENT ON TABLE "products" IS 'Product catalog with pricing and inventory';
COMMENT ON TABLE "orders" IS 'Customer orders with status and totals. customer_id references customers.id';
COMMENT ON TABLE "order_items" IS 'Individual line items within each order. order_id references orders.id, product_id references products.id';
COMMENT ON COLUMN "customers"."email" IS 'Customer email address, must be unique';
COMMENT ON COLUMN "products"."price" IS 'Current price per unit in USD';
COMMENT ON COLUMN "products"."stock_quantity" IS 'Number of units available in inventory';
COMMENT ON COLUMN "orders"."customer_id" IS 'References customers.id';
COMMENT ON COLUMN "orders"."status" IS 'Order processing status: pending, processing, completed, or cancelled';
COMMENT ON COLUMN "orders"."total_amount" IS 'Total order amount including all items';
COMMENT ON COLUMN "order_items"."order_id" IS 'References orders.id';
COMMENT ON COLUMN "order_items"."product_id" IS 'References products.id';
COMMENT ON COLUMN "order_items"."quantity" IS 'Number of units of this product in the order';
COMMENT ON COLUMN "order_items"."unit_price" IS 'Price per unit at time of order (may differ from current product price)';