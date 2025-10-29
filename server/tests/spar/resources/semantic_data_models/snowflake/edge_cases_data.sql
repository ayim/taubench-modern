-- Test Data for Snowflake Edge Cases (Simplified)
-- Focus on core Snowflake types: VARIANT, ARRAY, OBJECT
-- VARIANT data
INSERT INTO
  "products_with_variant" ("name", "metadata", "specifications")
SELECT
  'Smart Watch',
  PARSE_JSON('{"brand": "TechCorp", "color": "black"}'),
  PARSE_JSON('{"display": "AMOLED", "battery": "48h"}')
UNION ALL
SELECT
  'Wireless Earbuds',
  PARSE_JSON('{"brand": "AudioMax", "color": "white"}'),
  PARSE_JSON('{"drivers": "10mm", "battery": "8h"}');
INSERT INTO
  "events_with_variant" ("event_type", "payload")
SELECT
  'user_login',
  PARSE_JSON('{"user_id": 1, "device": "desktop"}')
UNION ALL
SELECT
  'purchase',
  PARSE_JSON('{"order_id": "ORD-001", "amount": 299.99}');
-- ARRAY data
INSERT INTO
  "products_with_arrays" ("name", "tags", "category_ids")
SELECT
  'Gaming Laptop',
  ARRAY_CONSTRUCT('gaming', 'laptop', 'portable'),
  ARRAY_CONSTRUCT(1, 5, 12)
UNION ALL
SELECT
  'Mechanical Keyboard',
  ARRAY_CONSTRUCT('keyboard', 'mechanical', 'rgb'),
  ARRAY_CONSTRUCT(1, 3);
-- OBJECT data
INSERT INTO
  "customers_with_objects" ("name", "email", "address", "contact_info")
SELECT
  'Alice Johnson',
  'alice@example.com',
  OBJECT_CONSTRUCT(
    'street',
    '123 Main St',
    'city',
    'San Francisco',
    'state',
    'CA'
  ),
  OBJECT_CONSTRUCT('phone', '+1-415-555-0100', 'preferred', 'email')
UNION ALL
SELECT
  'Bob Smith',
  'bob@example.com',
  OBJECT_CONSTRUCT(
    'street',
    '456 Oak Ave',
    'city',
    'New York',
    'state',
    'NY'
  ),
  OBJECT_CONSTRUCT('phone', '+1-212-555-0200', 'preferred', 'phone');