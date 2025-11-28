-- Test Data for MySQL E-commerce Schema
-- MySQL-specific syntax for INSERT statements
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
    shipping_address
  )
VALUES
  (
    1,
    '2024-01-20 11:30:00',
    'completed',
    1379.98,
    '123 Main St, Springfield, IL 62701'
  ),
  (
    1,
    '2024-02-15 14:20:00',
    'completed',
    42.98,
    '123 Main St, Springfield, IL 62701'
  ),
  (
    2,
    '2024-02-25 09:45:00',
    'completed',
    339.98,
    '456 Oak Ave, Portland, OR 97201'
  ),
  (
    2,
    '2024-03-05 16:10:00',
    'processing',
    649.98,
    '456 Oak Ave, Portland, OR 97201'
  ),
  (
    3,
    '2024-03-15 10:00:00',
    'completed',
    12.99,
    '789 Pine Rd, Austin, TX 78701'
  ),
  (
    3,
    '2024-03-20 13:30:00',
    'cancelled',
    399.99,
    '789 Pine Rd, Austin, TX 78701'
  ),
  (
    4,
    '2024-04-10 15:45:00',
    'pending',
    119.98,
    '321 Elm St, Seattle, WA 98101'
  );
-- Insert order items
INSERT INTO
  order_items (order_id, product_id, quantity, unit_price)
VALUES
  (1, 1, 1, 1299.99),
  (1, 3, 1, 89.99),
  (2, 2, 1, 29.99),
  (2, 7, 1, 12.99),
  (3, 5, 1, 249.99),
  (3, 4, 2, 49.99),
  (4, 6, 1, 399.99),
  (4, 5, 1, 249.99),
  (5, 7, 1, 12.99),
  (6, 6, 1, 399.99),
  (7, 3, 1, 89.99),
  (7, 2, 1, 29.99);
-- Insert comparison data
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
    1250.00,
    1200.00,
    5,
    1250.00,
    1250.00,
    5,
    '2024-01-10 10:00:00',
    '2024-01-10 10:00:00',
    'EXPORTED'
  ),
  (
    'invoice_002.pdf',
    3500.50,
    3450.00,
    12,
    3500.50,
    3500.50,
    12,
    '2024-01-11 11:30:00',
    '2024-01-11 11:30:00',
    'EXPORTED'
  ),
  (
    'invoice_003.pdf',
    850.00,
    840.00,
    3,
    850.00,
    850.00,
    3,
    '2024-01-12 09:15:00',
    '2024-01-12 09:15:00',
    'INIT'
  ),
  (
    'invoice_004.pdf',
    12000.00,
    11850.00,
    25,
    12000.00,
    12000.00,
    25,
    '2024-01-13 14:45:00',
    '2024-01-13 14:45:00',
    'EXPORTED'
  ),
  (
    'invoice_005.pdf',
    450.00,
    445.00,
    2,
    450.00,
    450.00,
    2,
    '2024-01-14 16:20:00',
    '2024-01-14 16:20:00',
    'INIT'
  );
-- Insert comprehensive data type test data
INSERT INTO
  mysql_data_types_test (
    tinyint_col,
    smallint_col,
    mediumint_col,
    int_col,
    bigint_col,
    decimal_col,
    numeric_col,
    float_col,
    double_col,
    bool_col,
    char_col,
    varchar_col,
    tinytext_col,
    text_col,
    mediumtext_col,
    longtext_col,
    binary_col,
    varbinary_col,
    tinyblob_col,
    blob_col,
    date_col,
    datetime_col,
    timestamp_col,
    time_col,
    year_col,
    json_col,
    enum_col,
    set_col,
    point_col
  )
VALUES
  (
    -- Numeric types
    127,
    32000,
    8000000,
    2147483647,
    9223372036854775807,
    12345.67,
    12345.678,
    123.45,
    123456.789,
    TRUE,
    -- String types
    'CHAR',
    'Variable length string example',
    'Tiny text',
    'Regular text column example',
    'Medium text content',
    'Long text content example',
    -- Binary types
    UNHEX('0123456789ABCDEF0123456789ABCDEF'),
    UNHEX('DEADBEEF'),
    UNHEX('CAFE'),
    UNHEX('BABE'),
    -- Date and time types
    '2024-01-15',
    '2024-01-15 10:30:00',
    '2024-01-15 10:30:00',
    '10:30:00',
    2024,
    -- JSON
    '{"name": "Product A", "price": 99.99, "tags": ["electronics", "sale"]}',
    -- Enum and Set
    'medium',
    'red,blue',
    -- Spatial
    ST_GeomFromText('POINT(1 1)')
  ),
  (
    -- Numeric types
    -128,
    -32000,
    -8000000,
    -2147483648,
    -9223372036854775808,
    -999.99,
    -888.777,
    -12.34,
    -9876.543,
    FALSE,
    -- String types
    'TEST',
    'Another varchar example',
    'Small',
    'More text here',
    'Medium sized text',
    'Very long text content',
    -- Binary types
    UNHEX('FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF'),
    UNHEX('12345678'),
    UNHEX('ABCD'),
    UNHEX('DCBA'),
    -- Date and time types
    '2023-12-31',
    '2023-12-31 23:59:59',
    '2023-12-31 23:59:59',
    '23:59:59',
    2023,
    -- JSON
    '{"user": "Alice", "age": 30, "active": true, "orders": [1, 2, 3]}',
    -- Enum and Set
    'large',
    'green,yellow',
    -- Spatial
    ST_GeomFromText('POINT(10 20)')
  ),
  (
    -- Numeric types with NULLs
    0,
    0,
    0,
    42,
    1000000,
    0.00,
    0.000,
    0.0,
    0.0,
    TRUE,
    -- String types
    'NULL TEST',
    'Testing NULL values',
    NULL,
    NULL,
    NULL,
    NULL,
    -- Binary types
    NULL,
    NULL,
    NULL,
    NULL,
    -- Date and time types
    '2024-06-15',
    '2024-06-15 12:00:00',
    '2024-06-15 12:00:00',
    '12:00:00',
    2024,
    -- JSON with NULL
    '{"status": null, "message": "Test with null"}',
    -- Enum and Set
    'small',
    'red',
    -- Spatial
    ST_GeomFromText('POINT(0 0)')
  ),
  (
    -- Edge case values
    1,
    100,
    50000,
    999999,
    123456789,
    999.99,
    777.777,
    3.14159,
    2.71828,
    FALSE,
    -- String types with special characters
    'SPE!@#$%^&',
    'String with "quotes" and ''apostrophes''',
    'Tiny',
    'Text\nwith\nnewlines',
    'Text with tabs\tand\tspaces',
    'UTF-8: 你好世界 🌍',
    -- Binary
    UNHEX('00'),
    UNHEX('FF'),
    UNHEX('AA'),
    UNHEX('55'),
    -- Date and time
    '2025-01-01',
    '2025-01-01 00:00:01',
    '2025-01-01 00:00:01',
    '00:00:01',
    2025,
    -- Complex JSON
    '{"array": [1, 2, 3], "nested": {"key": "value"}, "bool": false, "number": 123}',
    -- Enum and Set
    'x-large',
    'red,green,blue,yellow',
    -- Spatial
    ST_GeomFromText('POINT(-122.4194 37.7749)')
  ),
  (
    -- More realistic business data
    50,
    5000,
    500000,
    123456,
    987654321,
    1299.99,
    999.500,
    29.99,
    12345.6789,
    TRUE,
    -- Product-like strings
    'SKU123',
    'Laptop Pro 15" with Retina Display',
    'Electronics',
    'High-performance laptop with 16GB RAM and 512GB SSD',
    'Full product description with detailed specifications and features',
    'Extended warranty information and terms of service',
    -- Binary
    UNHEX('A1B2C3D4E5F6'),
    UNHEX('123456'),
    UNHEX('FEED'),
    UNHEX('BEEF'),
    -- Recent dates
    '2024-11-25',
    '2024-11-25 14:30:00',
    '2024-11-25 14:30:00',
    '14:30:00',
    2024,
    -- Product JSON
    '{"sku": "LAPTOP-001", "price": 1299.99, "stock": 25, "specs": {"ram": "16GB", "storage": "512GB"}}',
    -- Enum and Set
    'medium',
    'blue,green',
    -- Location point
    ST_GeomFromText('POINT(-73.9857 40.7484)')
  );
-- Insert invoice documents with JSON data for testing complex JSON operations
INSERT INTO
  invoice_documents (
    document_id,
    document_title,
    document_layout,
    model_type,
    content_extracted,
    content_translated,
    created_at,
    updated_at
  )
VALUES
  (
    'doc-001',
    'Koch Invoice March 2025.pdf',
    'standard',
    'koch_invoices',
    '{"customer": {"name": "Koch Energy Services, LLC", "email": "koch@example.com", "address": "123 Main St"}, "line_items": [{"description": "Gas delivery", "amount": 100000, "volume": 10000, "price": 10.0}, {"description": "Transport fee", "amount": 50000, "volume": 5000, "price": 10.0}], "invoice_total": 150000, "invoice_number": "INV-001", "invoice_date": "2025-03-01"}',
    '{"Buyer": {"name": "Koch Energy Services, LLC", "email": "koch@example.com", "address": "123 Main St"}, "Transactions": [{"description": "Gas delivery", "amount": 100000, "volume": 10000, "price": 10.0}, {"description": "Transport fee", "amount": 50000, "volume": 5000, "price": 10.0}], "Invoice_details": {"invoice_total": 150000, "invoice_number": "INV-001", "invoice_date": "2025-03-01"}}',
    '2025-03-01 10:00:00',
    '2025-03-01 10:00:00'
  ),
  (
    'doc-002',
    'Acme Corp Invoice April 2025.pdf',
    'standard',
    'acme_invoices',
    '{"customer": {"name": "Acme Corporation", "email": "billing@acme.com", "address": "456 Business Ave"}, "line_items": [{"description": "Product A", "amount": 75000, "volume": 150, "price": 500.0}, {"description": "Product B", "amount": 25000, "volume": 50, "price": 500.0}], "invoice_total": 100000, "invoice_number": "INV-002", "invoice_date": "2025-04-01"}',
    '{"Buyer": {"name": "Acme Corporation", "email": "billing@acme.com", "address": "456 Business Ave"}, "Transactions": [{"description": "Product A", "amount": 75000, "volume": 150, "price": 500.0}, {"description": "Product B", "amount": 25000, "volume": 50, "price": 500.0}], "Invoice_details": {"invoice_total": 100000, "invoice_number": "INV-002", "invoice_date": "2025-04-01"}}',
    '2025-04-01 11:00:00',
    '2025-04-01 11:00:00'
  ),
  (
    'doc-003',
    'GlobalTech Invoice May 2025.pdf',
    'detailed',
    'global_invoices',
    '{"customer": {"name": "GlobalTech Industries", "email": "ap@globaltech.com", "address": "789 Corporate Blvd"}, "line_items": [{"description": "Service Contract", "amount": 200000, "volume": 1, "price": 200000.0}], "invoice_total": 200000, "invoice_number": "INV-003", "invoice_date": "2025-05-01"}',
    '{"Buyer": {"name": "GlobalTech Industries", "email": "ap@globaltech.com", "address": "789 Corporate Blvd"}, "Transactions": [{"description": "Service Contract", "amount": 200000, "volume": 1, "price": 200000.0}], "Invoice_details": {"invoice_total": 200000, "invoice_number": "INV-003", "invoice_date": "2025-05-01"}}',
    '2025-05-01 09:00:00',
    '2025-05-01 09:00:00'
  );