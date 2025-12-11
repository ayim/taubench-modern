-- Test Data for E-commerce Schema
-- This file contains INSERT statements that should work across SQL dialects

-- Insert customers
INSERT INTO
  customers (name, email, created_at)
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
  products (
    name,
    description,
    price,
    category,
    stock_quantity,
    created_at
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
  orders (
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
  order_items (order_id, product_id, quantity, unit_price)
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

-- Insert comparison data for invoice comparison testing
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
    'Anahau June 2024.pdf',
    NULL,
    NULL,
    NULL,
    71878.0,
    71878.0,
    14,
    '2025-10-07 15:32:35.779069+00',
    '2025-10-07 15:32:35.779069+00',
    'EXPORTED'
  ),
  (
    'ARM ENERGY MANAGEMENT_August2025.pdf',
    -7951684.47,
    -9513894.1,
    126,
    0.0,
    -7965158.96,
    124,
    '2025-09-18 14:29:29.826598+00',
    '2025-09-18 16:33:50.959048+00',
    'INIT'
  ),
  (
    'Chevron Nat Gas_August2025.pdf',
    0.0,
    0.0,
    0,
    -3422102.6,
    -1475169.21,
    65,
    '2025-09-16 13:27:57.694478+00',
    '2025-09-23 14:15:56.816862+00',
    'EXPORTED'
  ),
  (
    'Chord_August2025.pdf',
    1081621.85,
    1081621.85,
    34,
    1081621.85,
    1081621.85,
    34,
    '2025-09-17 15:52:42.508661+00',
    '2025-09-17 17:34:13.868715+00',
    'EXPORTED'
  ),
  (
    'Cima_August2025_2.pdf',
    NULL,
    NULL,
    NULL,
    0.0,
    352381.65,
    181,
    '2025-09-22 21:54:55.617853+00',
    '2025-09-23 00:28:46.896958+00',
    'INIT'
  ),
  (
    'Cima_August2025.pdf',
    352381.65,
    352381.65,
    181,
    352381.65,
    4987833.26,
    153,
    '2025-09-17 16:03:47.384316+00',
    '2025-09-29 15:19:43.824097+00',
    'INIT'
  ),
  (
    'Colorado_August2025.pdf',
    -370146.88,
    -370146.88,
    28,
    -370146.88,
    -370146.88,
    28,
    '2025-09-17 16:03:06.280908+00',
    '2025-09-17 17:40:54.997079+00',
    'EXPORTED'
  ),
  (
    'Concord_August2025.pdf',
    3248636.14,
    3248635.49,
    135,
    3248636.14,
    3248636.14,
    138,
    '2025-09-16 17:49:37.948984+00',
    '2025-09-17 17:36:15.430861+00',
    'EXPORTED'
  ),
  (
    'Enterprise Products_August2025_2.pdf',
    4556049.28,
    4556049.26,
    314,
    4556049.28,
    4556049.26,
    314,
    '2025-09-23 00:59:59.460129+00',
    '2025-09-23 00:59:59.460129+00',
    'EXPORTED'
  ),
  (
    'Enterprise Products_August2025.pdf',
    4556049.28,
    4556049.26,
    314,
    -1302492.28,
    1826645.82,
    81,
    '2025-09-17 16:07:26.731322+00',
    '2025-09-29 14:30:10.84339+00',
    'EXPORTED'
  ),
  (
    'FLORIDA POWER AND LIGHT CO_August2025.pdf',
    -2910783.69,
    -2910783.69,
    67,
    -2910783.69,
    -2910783.69,
    67,
    '2025-09-17 15:48:15.133801+00',
    '2025-09-17 17:45:33.473903+00',
    'EXPORTED'
  ),
  (
    'JP_August2025.pdf',
    1316303.87,
    1316303.87,
    86,
    1316303.87,
    1316303.87,
    86,
    '2025-09-17 16:08:05.116562+00',
    '2025-09-17 19:21:11.019975+00',
    'EXPORTED'
  ),
  (
    'Macquarie_August2025_2.pdf',
    NULL,
    NULL,
    NULL,
    -920213.84,
    -10500991.37,
    99,
    '2025-09-22 21:55:25.226636+00',
    '2025-09-23 00:29:17.803162+00',
    'INIT'
  ),
  (
    'Macquarie_August2025.pdf',
    -920213.84,
    -907044.36,
    967,
    -920213.84,
    -832038.8,
    74,
    '2025-09-17 16:29:22.216086+00',
    '2025-09-19 17:43:25.860311+00',
    'INIT'
  ),
  (
    'Mieco_August2025_2.pdf',
    NULL,
    NULL,
    NULL,
    294828.8,
    8164883.04,
    494,
    '2025-09-22 21:41:34.494904+00',
    '2025-09-22 21:41:34.494904+00',
    'INIT'
  ),
  (
    'Mieco_August2025.pdf',
    -294828.8,
    -294828.8,
    494,
    -294828.8,
    2687804.36,
    786,
    '2025-09-17 16:08:43.496995+00',
    '2025-09-29 17:05:48.664108+00',
    'INIT'
  ),
  (
    'Nextera_August2025.pdf',
    8332.66,
    8332.66,
    2,
    8332.66,
    8332.66,
    2,
    '2025-09-18 19:54:19.060069+00',
    '2025-09-19 11:39:39.389447+00',
    'EXPORTED'
  ),
  (
    'Occidental_August2025.pdf',
    14057548.23,
    14057548.23,
    431,
    14057548.23,
    14057548.23,
    431,
    '2025-09-18 20:03:27.171389+00',
    '2025-09-18 20:43:43.044494+00',
    'EXPORTED'
  ),
  (
    'Pacific Gas and Electric Company Core_August2025.pdf',
    489954.22,
    489954.22,
    44,
    489954.22,
    489954.22,
    44,
    '2025-09-16 13:22:50.296657+00',
    '2025-09-16 14:52:07.76277+00',
    'EXPORTED'
  ),
  (
    'PROTEGE ENERGY III LLC_August2025.pdf',
    1641705.0,
    1641705.0,
    62,
    1641705.0,
    1641705.0,
    31,
    '2025-09-18 19:37:54.434282+00',
    '2025-09-18 19:56:20.126831+00',
    'EXPORTED'
  ),
  (
    'Sempra_August2025.pdf',
    -511128.36,
    -511128.36,
    128,
    -511128.36,
    -511128.36,
    128,
    '2025-09-18 19:44:33.337793+00',
    '2025-09-18 19:58:07.529732+00',
    'EXPORTED'
  ),
  (
    'Sequent_August2025.pdf',
    4779503.48,
    4779503.48,
    222,
    4779503.48,
    4779503.58,
    222,
    '2025-09-18 19:34:00.997615+00',
    '2025-09-18 20:52:14.637236+00',
    'EXPORTED'
  ),
  (
    'Spotlight_August2025.pdf',
    -1386167.92,
    -1386167.92,
    147,
    -1065387.8,
    -1065387.8,
    122,
    '2025-09-17 15:00:59.781024+00',
    '2025-09-19 14:44:05.468232+00',
    'EXPORTED'
  ),
  (
    'TEXLA ENERGY MANAGEMENT INC_August2025.pdf',
    264015.58,
    264015.58,
    47,
    264015.58,
    264015.58,
    47,
    '2025-09-17 16:05:50.337899+00',
    '2025-09-17 19:13:37.942376+00',
    'EXPORTED'
  ),
  (
    'United Energy_August2025_2.pdf',
    7683344.91,
    7683344.99,
    181,
    7683344.91,
    7683344.99,
    181,
    '2025-09-22 21:48:10.933659+00',
    '2025-09-23 00:59:45.542133+00',
    'EXPORTED'
  ),
  (
    'United Energy_August2025.pdf',
    7683344.91,
    7683344.99,
    181,
    7683344.91,
    7683344.99,
    181,
    '2025-09-18 19:16:14.470895+00',
    '2025-09-29 16:04:58.685807+00',
    'INIT'
  ),
  (
    'WORLD FUEL SERVICES INC_August2025.pdf',
    -4756262.2,
    1362997.12,
    25,
    -4756262.23,
    -4756262.23,
    228,
    '2025-09-18 19:45:22.338508+00',
    '2025-09-19 12:21:48.130325+00',
    'EXPORTED'
  );

