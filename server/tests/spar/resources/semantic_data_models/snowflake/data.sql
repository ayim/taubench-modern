-- Test Data for E-commerce Schema (Snowflake)
-- Using QUOTED identifiers to preserve lowercase names for test compatibility
-- Insert customers
INSERT INTO
  "customers" ("name", "email", "created_at")
VALUES
  (
    'Alice Johnson',
    'alice.johnson@example.com',
    '2024-01-15 10:00:00'
  ),
  (
    'Bob Smith',
    'bob.smith@example.com',
    '2024-02-20 14:30:00'
  ),
  (
    'Carol White',
    'carol.white@example.com',
    '2024-03-10 09:15:00'
  ),
  (
    'David Brown',
    'david.brown@example.com',
    '2024-04-05 16:45:00'
  );
-- Insert products
INSERT INTO
  "products" (
    "name",
    "description",
    "price",
    "category",
    "stock_quantity",
    "created_at"
  )
VALUES
  (
    'Laptop Pro 15"',
    'High-performance laptop with 15-inch display',
    1299.99,
    'Electronics',
    25,
    '2024-01-01 00:00:00'
  ),
  (
    'Wireless Mouse',
    'Ergonomic wireless mouse with USB receiver',
    29.99,
    'Electronics',
    150,
    '2024-01-01 00:00:00'
  ),
  (
    'Mechanical Keyboard',
    'RGB mechanical gaming keyboard',
    89.99,
    'Electronics',
    75,
    '2024-01-01 00:00:00'
  ),
  (
    'USB-C Hub',
    '7-in-1 USB-C hub with HDMI and card reader',
    49.99,
    'Electronics',
    100,
    '2024-01-01 00:00:00'
  ),
  (
    'Office Chair',
    'Ergonomic office chair with lumbar support',
    249.99,
    'Furniture',
    30,
    '2024-01-01 00:00:00'
  ),
  (
    'Standing Desk',
    'Adjustable height standing desk',
    399.99,
    'Furniture',
    15,
    '2024-01-01 00:00:00'
  ),
  (
    'Coffee Mug',
    'Ceramic coffee mug with handle',
    12.99,
    'Kitchen',
    200,
    '2024-01-01 00:00:00'
  ),
  (
    'Water Bottle',
    'Stainless steel insulated water bottle',
    24.99,
    'Kitchen',
    80,
    '2024-01-01 00:00:00'
  );
-- Insert orders
INSERT INTO
  "orders" (
    "customer_id",
    "order_date",
    "status",
    "total_amount",
    "shipping_address",
    "notes"
  )
VALUES
  (
    1,
    '2024-01-20 11:30:00',
    'completed',
    1329.98,
    '123 Main St, Apt 4B, New York, NY 10001',
    'Please leave at front desk'
  ),
  (
    1,
    '2024-02-15 09:45:00',
    'completed',
    262.97,
    '123 Main St, Apt 4B, New York, NY 10001',
    NULL
  ),
  (
    2,
    '2024-02-25 14:20:00',
    'completed',
    649.98,
    '456 Oak Ave, San Francisco, CA 94102',
    'Call before delivery'
  ),
  (
    2,
    '2024-03-10 16:00:00',
    'processing',
    89.99,
    '456 Oak Ave, San Francisco, CA 94102',
    NULL
  ),
  (
    3,
    '2024-03-15 10:15:00',
    'completed',
    37.98,
    '789 Pine Rd, Austin, TX 78701',
    NULL
  ),
  (
    3,
    '2024-04-01 13:30:00',
    'pending',
    1299.99,
    '789 Pine Rd, Austin, TX 78701',
    'Birthday gift - please gift wrap'
  ),
  (
    4,
    '2024-04-10 15:45:00',
    'cancelled',
    399.99,
    '321 Elm St, Seattle, WA 98101',
    'Customer changed mind'
  );
-- Insert order items
INSERT INTO
  "order_items" (
    "order_id",
    "product_id",
    "quantity",
    "unit_price"
  )
VALUES
  -- Order 1 (Alice's first order - laptop and mouse)
  (1, 1, 1, 1299.99),
  (1, 2, 1, 29.99),
  -- Order 2 (Alice's second order - office chair and accessories)
  (2, 5, 1, 249.99),
  (2, 7, 1, 12.99),
  -- Order 3 (Bob's first order - standing desk and chair)
  (3, 6, 1, 399.99),
  (3, 5, 1, 249.99),
  -- Order 4 (Bob's second order - keyboard)
  (4, 3, 1, 89.99),
  -- Order 5 (Carol's first order - kitchen items)
  (5, 7, 2, 12.99),
  (5, 8, 1, 24.99),
  -- Order 6 (Carol's second order - laptop)
  (6, 1, 1, 1299.99),
  -- Order 7 (David's cancelled order - standing desk)
  (7, 6, 1, 399.99);