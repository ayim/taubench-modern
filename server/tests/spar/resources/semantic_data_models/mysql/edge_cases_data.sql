-- Test Data for MySQL Edge Cases Schema
-- Comprehensive data covering all MySQL data types and edge cases
-- Insert products with JSON metadata
INSERT INTO
  products_with_json (name, metadata, specifications, tags)
VALUES
  (
    'Laptop Pro 15"',
    '{"brand": "TechCorp", "model": "Pro15", "warranty": "2 years"}',
    '{"cpu": "Intel i7", "ram": "16GB", "storage": "512GB SSD", "screen": {"size": 15.6, "resolution": "1920x1080"}}',
    '["electronics", "computers", "bestseller"]'
  ),
  (
    'Wireless Mouse',
    '{"brand": "Ergo", "color": "black", "connectivity": "bluetooth"}',
    '{"dpi": 1600, "buttons": 5, "battery": "rechargeable", "weight_grams": 85}',
    '["electronics", "accessories", "new"]'
  ),
  (
    'Standing Desk',
    '{"brand": "DeskPro", "material": "bamboo", "adjustable": true}',
    '{"height_range": {"min": 28, "max": 48}, "capacity_lbs": 200, "motor": "dual"}',
    '["furniture", "office", "featured"]'
  ),
  (
    'Coffee Maker',
    NULL,
    '{"capacity_cups": 12, "features": ["programmable", "auto-shutoff", "warming plate"]}',
    '["kitchen", "appliances"]'
  ),
  (
    'Notebook Set',
    '{"pages": 200, "ruled": true, "eco_friendly": true}',
    NULL,
    '["office", "stationery", "sale"]'
  );
-- Insert user preferences with JSON
INSERT INTO
  user_preferences (user_id, preferences, change_history)
VALUES
  (
    1,
    '{"theme": "dark", "language": "en", "notifications": {"email": true, "push": false, "sms": true}, "dashboard": {"layout": "grid", "widgets": ["sales", "inventory", "customers"]}}',
    '{"changes": [{"date": "2024-01-15", "field": "theme", "old": "light", "new": "dark"}]}'
  ),
  (
    2,
    '{"theme": "light", "language": "es", "timezone": "America/New_York", "display": {"density": "compact", "font_size": 14}}',
    '{"changes": [{"date": "2024-02-20", "field": "language", "old": "en", "new": "es"}, {"date": "2024-03-01", "field": "theme", "old": "dark", "new": "light"}]}'
  ),
  (
    3,
    '{"notifications": {"all": false}, "privacy": {"analytics": false, "cookies": {"essential": true, "marketing": false}}}',
    NULL
  ),
  (4, '{}', '{"changes": []}'),
  (
    5,
    '{"dashboard": {"widgets": []}, "experimental_features": {"beta_ui": true, "advanced_search": true}}',
    NULL
  );
-- Insert event logs with JSON payloads
INSERT INTO
  event_logs (event_type, payload, metadata)
VALUES
  (
    'user_login',
    '{"user_id": 1, "ip": "192.168.1.100", "device": "desktop", "browser": "Chrome"}',
    '{"session_id": "abc123", "location": {"country": "US", "city": "New York"}}'
  ),
  (
    'order_created',
    '{"order_id": 1001, "customer_id": 42, "items": [{"product_id": 1, "quantity": 2, "price": 99.99}], "total": 199.98}',
    '{"payment_method": "credit_card", "shipping": "express"}'
  ),
  (
    'product_updated',
    '{"product_id": 5, "changes": {"price": {"old": 49.99, "new": 39.99}, "stock": {"old": 100, "new": 150}}}',
    '{"updated_by": "admin", "reason": "inventory_adjustment"}'
  ),
  (
    'error_occurred',
    '{"error_code": "DB_TIMEOUT", "message": "Database connection timeout", "stack_trace": "...", "severity": "high"}',
    '{"service": "api-server", "version": "2.1.0"}'
  ),
  (
    'batch_processed',
    '{"batch_id": "batch_2024_001", "records_processed": 1000, "records_failed": 3, "duration_ms": 5432}',
    NULL
  );
-- Insert locations with JSON and spatial data
INSERT INTO
  locations (name, coordinates, address, location_point)
VALUES
  (
    'New York Office',
    '{"latitude": 40.7128, "longitude": -74.0060}',
    '{"street": "123 Main St", "city": "New York", "state": "NY", "zip": "10001", "country": "US"}',
    ST_GeomFromText('POINT(-74.0060 40.7128)')
  ),
  (
    'Los Angeles Warehouse',
    '{"latitude": 34.0522, "longitude": -118.2437}',
    '{"street": "456 Commerce Blvd", "city": "Los Angeles", "state": "CA", "zip": "90001", "country": "US"}',
    ST_GeomFromText('POINT(-118.2437 34.0522)')
  ),
  (
    'Chicago Store',
    '{"latitude": 41.8781, "longitude": -87.6298}',
    '{"street": "789 Retail Ave", "city": "Chicago", "state": "IL", "zip": "60601", "country": "US"}',
    ST_GeomFromText('POINT(-87.6298 41.8781)')
  ),
  (
    'International HQ',
    NULL,
    '{"city": "London", "country": "UK", "postcode": "SW1A 1AA"}',
    ST_GeomFromText('POINT(-0.1278 51.5074)')
  );
-- Insert advanced products
INSERT INTO
  advanced_products (
    sku,
    name,
    pricing_rules,
    category,
    product_tags,
    inventory_details,
    active
  )
VALUES
  (
    'ELEC-LAP-001',
    'Laptop Pro',
    '{"base_price": 1299.99, "discounts": [{"type": "bulk", "min_quantity": 5, "percent": 10}, {"type": "seasonal", "end_date": "2024-12-31", "percent": 15}]}',
    'electronics',
    'new,featured,bestseller',
    '{"warehouse": "W1", "stock": 25, "reserved": 3, "reorder_point": 10, "supplier": "TechSupply Inc"}',
    TRUE
  ),
  (
    'FURN-DSK-002',
    'Standing Desk',
    '{"base_price": 399.99, "markup": 1.4, "competitor_prices": [449.99, 429.99, 399.00]}',
    'furniture',
    'featured',
    '{"warehouse": "W2", "stock": 15, "reserved": 2, "shipping_weight_lbs": 85}',
    TRUE
  ),
  (
    'KITCH-MUG-003',
    'Coffee Mug',
    '{"base_price": 12.99, "cost": 4.50, "margin_percent": 65}',
    'kitchen',
    'sale,clearance',
    '{"warehouse": "W1", "stock": 500, "reserved": 0}',
    TRUE
  ),
  (
    'OFF-PEN-004',
    'Pen Set',
    '{"base_price": 19.99}',
    'office',
    NULL,
    '{"warehouse": "W3", "stock": 0, "backorder": true}',
    FALSE
  );
-- Insert temporal data test cases
INSERT INTO
  temporal_data_test (
    date_only,
    datetime_precise,
    time_only,
    time_precise,
    year_only
  )
VALUES
  (
    '2024-01-15',
    '2024-01-15 10:30:45.123456',
    '10:30:45',
    '10:30:45.123456',
    2024
  ),
  (
    '2023-12-31',
    '2023-12-31 23:59:59.999999',
    '23:59:59',
    '23:59:59.999999',
    2023
  ),
  (
    '2024-06-15',
    '2024-06-15 12:00:00.000000',
    '12:00:00',
    '12:00:00.000000',
    2024
  ),
  (
    '1999-01-01',
    '1999-01-01 00:00:00.000001',
    '00:00:00',
    '00:00:00.000001',
    1999
  ),
  (
    '2025-12-25',
    '2025-12-25 18:45:30.555555',
    '18:45:30',
    '18:45:30.555555',
    2025
  );
-- Insert numeric edge cases
INSERT INTO
  numeric_edge_cases (
    tiny_min,
    tiny_max,
    small_min,
    small_max,
    medium_min,
    medium_max,
    int_min,
    int_max,
    bigint_min,
    bigint_max,
    tiny_unsigned,
    small_unsigned,
    int_unsigned,
    bigint_unsigned,
    float_zero,
    float_negative,
    float_small,
    float_large,
    double_precision,
    decimal_precise,
    decimal_money,
    zero_int,
    zero_decimal
  )
VALUES
  -- Boundary values
  (
    -128,
    127,
    -32768,
    32767,
    -8388608,
    8388607,
    -2147483648,
    2147483647,
    -9223372036854775808,
    9223372036854775807,
    255,
    65535,
    4294967295,
    18446744073709551615,
    0.0,
    -123.456,
    0.000001,
    999999999.999999,
    123456789012345.67890,
    12345678901234567890123456789012345.123456789012345678901234567890,
    123456789012345.9999,
    0,
    0.00
  ),
  -- Zero and near-zero values
  (
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0,
    0.0,
    -0.0,
    0.0000000001,
    0.0,
    0.0,
    0.000000000000000000000000000001,
    0.0001,
    0,
    0.00
  ),
  -- Typical business values
  (
    42,
    100,
    5000,
    10000,
    500000,
    1000000,
    123456,
    9876543,
    123456789012,
    987654321098,
    200,
    50000,
    3000000,
    1000000000000,
    1.5,
    -99.99,
    0.01,
    12345.67,
    9999.9999,
    1299.990000000000000000000000000000,
    49.9900,
    1,
    99.99
  );
-- Insert string edge cases
INSERT INTO
  string_edge_cases (
    char_fixed,
    varchar_long,
    tiny_text,
    regular_text,
    medium_text,
    long_text,
    utf8_content,
    nullable_text,
    empty_varchar
  )
VALUES
  (
    'FIXED',
    'A relatively long VARCHAR string to test capacity',
    'Tiny text content',
    'Regular TEXT column with moderate content',
    'Medium text with more data that could be quite long',
    'Long text field capable of storing very large amounts of data',
    'UTF-8 content with emojis: 🌍 🚀 💻 Hello 你好 こんにちは مرحبا',
    'Not null text',
    ''
  ),
  (
    'TEST',
    REPEAT('X', 1000),
    'Small',
    REPEAT('Regular TEXT ', 100),
    REPEAT('Medium TEXT content ', 500),
    REPEAT('Long TEXT data ', 1000),
    'Special chars: <>&"'' àéîöü ñ',
    NULL,
    ''
  ),
  (
    '',
    'String with\nnewlines\nand\ttabs',
    'A',
    'Text with "quotes" and ''apostrophes''',
    'Multi\nLine\nText\nContent',
    'Text with special characters: !@#$%^&*()_+-=[]{}|:,.<>?',
    'Symbols: ©®™€¥£¢',
    'Sample text',
    ''
  ),
  (
    REPEAT('A', 255),
    '',
    '',
    '',
    '',
    '',
    '🎉🎊🎈🎁',
    '',
    ''
  ),
  (
    'EDGECASE',
    'Testing NULL handling and empty strings',
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    ''
  );
-- Insert binary edge cases
INSERT INTO
  binary_edge_cases (
    binary_fixed,
    varbinary_data,
    tiny_blob,
    regular_blob
  )
VALUES
  (
    UNHEX('0123456789ABCDEF0123456789ABCDEF'),
    UNHEX('DEADBEEF'),
    UNHEX('CAFE'),
    UNHEX('BABE')
  ),
  (
    UNHEX('FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF'),
    UNHEX('12345678'),
    UNHEX('FF'),
    UNHEX('ABCDEF')
  ),
  (
    UNHEX('00000000000000000000000000000000'),
    UNHEX('00'),
    UNHEX('00'),
    UNHEX('00')
  ),
  (NULL, NULL, NULL, NULL);
-- Insert ENUM and SET edge cases
INSERT INTO
  enum_set_edge_cases (
    size_enum,
    status_enum,
    permissions,
    features,
    nullable_enum,
    nullable_set
  )
VALUES
  (
    'small',
    'draft',
    'read',
    'feature_a',
    'yes',
    'option1'
  ),
  (
    'xxl',
    'approved',
    'read,write,delete',
    'feature_a,feature_b,feature_c,feature_d',
    'no',
    'option1,option2'
  ),
  (
    'medium',
    'in-progress',
    'read,write',
    'feature_a,feature_c',
    'maybe',
    'option1,option2,option3'
  ),
  (
    'xs',
    'pending-review',
    'read,write,delete,admin,superuser,audit,export,import',
    'feature_b',
    NULL,
    NULL
  ),
  ('5xl', 'rejected', '', '', 'yes', '');
-- Insert spatial edge cases
INSERT INTO
  spatial_edge_cases (
    point_location,
    line_route,
    poly_area,
    multi_point,
    multi_line,
    multi_poly,
    generic_geom,
    geom_collection
  )
VALUES
  (
    ST_GeomFromText('POINT(0 0)'),
    ST_GeomFromText('LINESTRING(0 0, 1 1, 2 2)'),
    ST_GeomFromText('POLYGON((0 0, 0 4, 4 4, 4 0, 0 0))'),
    ST_GeomFromText('MULTIPOINT(0 0, 1 1, 2 2)'),
    ST_GeomFromText('MULTILINESTRING((0 0, 1 1), (2 2, 3 3))'),
    ST_GeomFromText(
      'MULTIPOLYGON(((0 0, 0 1, 1 1, 1 0, 0 0)), ((2 2, 2 3, 3 3, 3 2, 2 2)))'
    ),
    ST_GeomFromText('POINT(5 5)'),
    ST_GeomFromText(
      'GEOMETRYCOLLECTION(POINT(0 0), LINESTRING(1 1, 2 2))'
    )
  ),
  (
    ST_GeomFromText('POINT(-122.4194 37.7749)'),
    ST_GeomFromText(
      'LINESTRING(-122.4194 37.7749, -122.4184 37.7759)'
    ),
    ST_GeomFromText(
      'POLYGON((-122.5 37.7, -122.5 37.8, -122.4 37.8, -122.4 37.7, -122.5 37.7))'
    ),
    ST_GeomFromText(
      'MULTIPOINT(-122.4194 37.7749, -122.4184 37.7759)'
    ),
    ST_GeomFromText(
      'MULTILINESTRING((-122.4194 37.7749, -122.4184 37.7759), (-122.4174 37.7769, -122.4164 37.7779))'
    ),
    ST_GeomFromText(
      'MULTIPOLYGON(((-122.5 37.7, -122.5 37.75, -122.45 37.75, -122.45 37.7, -122.5 37.7)))'
    ),
    ST_GeomFromText('LINESTRING(-122.4 37.7, -122.5 37.8)'),
    NULL
  ),
  (
    ST_GeomFromText('POINT(180 90)'),
    ST_GeomFromText('LINESTRING(180 90, -180 -90)'),
    ST_GeomFromText(
      'POLYGON((0 0, 0 10, 10 10, 10 0, 0 0), (2 2, 2 8, 8 8, 8 2, 2 2))'
    ),
    NULL,
    NULL,
    NULL,
    NULL,
    NULL
  );
-- Insert JSON complex structures
INSERT INTO
  json_complex_structures (
    json_null,
    json_bool,
    json_number,
    json_string,
    json_array_empty,
    json_array_numbers,
    json_array_strings,
    json_array_mixed,
    json_array_nested,
    json_object_empty,
    json_object_simple,
    json_object_nested,
    json_object_arrays,
    json_complex
  )
VALUES
  (
    'null',
    'true',
    '42',
    '"Hello World"',
    '[]',
    '[1, 2, 3, 4, 5]',
    '["apple", "banana", "cherry"]',
    '[1, "two", true, null]',
    '[[1, 2], [3, 4], [5, 6]]',
    '{}',
    '{"name": "John", "age": 30}',
    '{"user": {"name": "Alice", "profile": {"age": 25, "city": "NYC"}}}',
    '{"numbers": [1, 2, 3], "strings": ["a", "b", "c"]}',
    '{"users": [{"id": 1, "name": "Alice", "active": true}, {"id": 2, "name": "Bob", "active": false}], "total": 2, "metadata": {"version": "1.0", "cached": true}}'
  ),
  (
    'null',
    'false',
    '3.14159',
    '""',
    '[]',
    '[0, -1, 100, 9999999]',
    '[]',
    '[]',
    '[[], [[]], [[], [[]]]]',
    '{}',
    '{"status": "active"}',
    '{"company": {"name": "TechCorp", "address": {"street": "123 Main", "city": "SF", "coords": {"lat": 37.7, "lon": -122.4}}}}',
    '{"empty": [], "single": [1], "multiple": [1, 2, 3]}',
    '{"data": null, "error": {"code": 404, "message": "Not found", "details": null}}'
  ),
  (
    'null',
    'true',
    '0',
    '"Special chars: \\"quotes\\", newlines\\n, tabs\\t"',
    '[]',
    '[1]',
    '["single"]',
    '[null]',
    '[[[[[[1]]]]]]',
    '{}',
    '{"key": "value"}',
    '{"level1": {"level2": {"level3": {"level4": {"level5": "deep"}}}}}',
    '{"matrix": [[1, 2], [3, 4]], "vector": [5, 6, 7]}',
    '{"type": "product", "id": 123, "name": "Laptop", "price": 999.99, "tags": ["electronics", "computers"], "specs": {"cpu": "i7", "ram": 16}, "available": true, "reviews": [{"user": "Alice", "rating": 5}, {"user": "Bob", "rating": 4}]}'
  ),
  (
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL,
    NULL
  ),
  (
    'null',
    'true',
    '-999.99',
    '"UTF-8: 你好 🌍"',
    '[]',
    '[-1, 0, 1]',
    '["first", "", "last"]',
    '[true, false, null, 0, ""]',
    '[[]]',
    '{}',
    '{"a": 1, "b": 2, "c": 3}',
    '{"top": {"mid": {"bot": "value"}}}',
    '{"a": [1], "b": [2, 3], "c": [4, 5, 6]}',
    '{"empty_obj": {}, "empty_arr": [], "null_val": null, "nested": {"also_empty": {}}}'
  );