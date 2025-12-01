-- Test Data for E-commerce Schema (Redshift-specific)
-- Redshift requires explicit ID values (no SERIAL auto-increment)
-- Uses explicit column lists including id columns
-- Insert customers
INSERT INTO
  customers (id, name, email, created_at, updated_at)
VALUES
  (
    1,
    'Alice Johnson',
    'alice.johnson@example.com',
    '2024-01-15 10:00:00',
    '2024-01-15 10:00:00'
  ),
  (
    2,
    'Bob Smith',
    'bob.smith@example.com',
    '2024-02-20 14:30:00',
    '2024-02-20 14:30:00'
  ),
  (
    3,
    'Carol White',
    'carol.white@example.com',
    '2024-03-10 09:15:00',
    '2024-03-10 09:15:00'
  ),
  (
    4,
    'David Brown',
    'david.brown@example.com',
    '2024-04-05 16:45:00',
    '2024-04-05 16:45:00'
  );
-- Insert products
INSERT INTO
  products (
    id,
    name,
    description,
    price,
    category,
    stock_quantity,
    created_at,
    updated_at
  )
VALUES
  (
    1,
    'Laptop Pro 15"',
    'High-performance laptop with 15-inch display',
    1299.99,
    'Electronics',
    25,
    '2024-01-01 00:00:00',
    '2024-01-01 00:00:00'
  ),
  (
    2,
    'Wireless Mouse',
    'Ergonomic wireless mouse with USB receiver',
    29.99,
    'Electronics',
    150,
    '2024-01-01 00:00:00',
    '2024-01-01 00:00:00'
  ),
  (
    3,
    'Mechanical Keyboard',
    'RGB mechanical gaming keyboard',
    89.99,
    'Electronics',
    75,
    '2024-01-01 00:00:00',
    '2024-01-01 00:00:00'
  ),
  (
    4,
    'USB-C Hub',
    '7-in-1 USB-C hub with HDMI and card reader',
    49.99,
    'Electronics',
    100,
    '2024-01-01 00:00:00',
    '2024-01-01 00:00:00'
  ),
  (
    5,
    'Office Chair',
    'Ergonomic office chair with lumbar support',
    249.99,
    'Furniture',
    30,
    '2024-01-01 00:00:00',
    '2024-01-01 00:00:00'
  ),
  (
    6,
    'Standing Desk',
    'Adjustable height standing desk',
    399.99,
    'Furniture',
    15,
    '2024-01-01 00:00:00',
    '2024-01-01 00:00:00'
  ),
  (
    7,
    'Coffee Mug',
    'Ceramic coffee mug with handle',
    12.99,
    'Kitchen',
    200,
    '2024-01-01 00:00:00',
    '2024-01-01 00:00:00'
  ),
  (
    8,
    'Water Bottle',
    'Stainless steel insulated water bottle',
    24.99,
    'Kitchen',
    80,
    '2024-01-01 00:00:00',
    '2024-01-01 00:00:00'
  );
-- Insert orders
INSERT INTO
  orders (
    id,
    customer_id,
    order_date,
    status,
    total_amount,
    shipping_address,
    notes
  )
VALUES
  (
    1,
    1,
    '2024-01-20 11:30:00',
    'completed',
    1329.98,
    '123 Main St, Apt 4B, New York, NY 10001',
    'Please leave at front desk'
  ),
  (
    2,
    1,
    '2024-02-15 09:45:00',
    'completed',
    262.97,
    '123 Main St, Apt 4B, New York, NY 10001',
    NULL
  ),
  (
    3,
    2,
    '2024-02-25 14:20:00',
    'completed',
    649.98,
    '456 Oak Ave, San Francisco, CA 94102',
    'Call before delivery'
  ),
  (
    4,
    2,
    '2024-03-10 16:00:00',
    'processing',
    89.99,
    '456 Oak Ave, San Francisco, CA 94102',
    NULL
  ),
  (
    5,
    3,
    '2024-03-15 10:15:00',
    'completed',
    37.98,
    '789 Pine Rd, Austin, TX 78701',
    NULL
  ),
  (
    6,
    3,
    '2024-04-01 13:30:00',
    'pending',
    1699.98,
    '789 Pine Rd, Austin, TX 78701',
    'Gift wrap requested'
  ),
  (
    7,
    4,
    '2024-04-10 08:00:00',
    'completed',
    119.98,
    '321 Elm St, Seattle, WA 98101',
    NULL
  ),
  (
    8,
    4,
    '2024-04-15 17:30:00',
    'cancelled',
    399.99,
    '321 Elm St, Seattle, WA 98101',
    'Customer requested cancellation'
  );
-- Insert order_items
INSERT INTO
  order_items (id, order_id, product_id, quantity, unit_price)
VALUES
  (1, 1, 1, 1, 1299.99),
  (2, 1, 2, 1, 29.99),
  (3, 2, 5, 1, 249.99),
  (4, 2, 7, 1, 12.99),
  (5, 3, 6, 1, 399.99),
  (6, 3, 5, 1, 249.99),
  (7, 4, 3, 1, 89.99),
  (8, 5, 2, 1, 29.99),
  (9, 5, 4, 1, 7.99),
  (10, 6, 1, 1, 1299.99),
  (11, 6, 6, 1, 399.99),
  (12, 7, 7, 5, 12.99),
  (13, 7, 8, 2, 24.99),
  (14, 8, 6, 1, 399.99);
-- Insert comparison_v1_v2 data
INSERT INTO
  comparison_v1_v2 (
    document_name,
    v1_invoice_total,
    v1_line_items_total,
    v1_line_items_count,
    v2_invoice_total,
    v2_line_items_total,
    v2_line_items_count,
    created_at,
    updated_at,
    export_status
  )
VALUES
  (
    'invoice_001.pdf',
    1500.00,
    1500.00,
    3,
    1500.00,
    1500.00,
    3,
    '2024-01-15 10:00:00',
    '2024-01-15 10:05:00',
    'EXPORTED'
  ),
  (
    'invoice_002.pdf',
    2750.50,
    2750.50,
    5,
    2750.50,
    2750.50,
    5,
    '2024-01-16 11:30:00',
    '2024-01-16 11:35:00',
    'EXPORTED'
  ),
  (
    'invoice_003.pdf',
    890.25,
    890.25,
    2,
    895.30,
    895.30,
    2,
    '2024-01-17 14:20:00',
    '2024-01-17 14:25:00',
    'EXPORTED'
  ),
  (
    'invoice_004.pdf',
    3200.00,
    3200.00,
    7,
    3200.00,
    3200.00,
    7,
    '2024-01-18 09:15:00',
    '2024-01-18 09:20:00',
    'INIT'
  ),
  (
    'invoice_005.pdf',
    567.80,
    567.80,
    1,
    567.80,
    567.80,
    1,
    '2024-01-19 16:45:00',
    '2024-01-19 16:50:00',
    'EXPORTED'
  );