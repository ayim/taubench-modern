-- Test Data for Edge Cases Schema
-- This file contains INSERT statements with special data types (JSON, JSONB, arrays, UUIDs)

-- Insert products with JSON metadata
INSERT INTO products_with_json (name, metadata, specifications, tags, external_id, created_at) VALUES
    (
        'Smart Watch Pro',
        '{"brand": "TechCorp", "warranty_years": 2, "water_resistant": true}',
        '{"display": {"size_inches": 1.4, "resolution": "454x454", "type": "AMOLED"}, "battery": {"capacity_mah": 300, "life_days": 7}, "sensors": ["heart_rate", "accelerometer", "gyroscope", "gps"]}',
        ARRAY['electronics', 'wearable', 'fitness'],
        'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
        '2024-01-01 00:00:00'
    ),
    (
        'Wireless Earbuds',
        '{"brand": "AudioTech", "warranty_years": 1, "noise_cancelling": true}',
        '{"audio": {"driver_size_mm": 10, "frequency_range": "20Hz-20kHz", "impedance_ohms": 16}, "battery": {"earbuds_hours": 6, "case_hours": 24}, "features": ["anc", "ambient_mode", "touch_controls"]}',
        ARRAY['electronics', 'audio', 'wireless'],
        'b1ffcd99-9d1c-4ef8-bb6d-6bb9bd380a22',
        '2024-01-01 00:00:00'
    ),
    (
        'Gaming Laptop',
        '{"brand": "GamePro", "warranty_years": 3, "vr_ready": true}',
        '{"cpu": {"model": "Intel i9-13900H", "cores": 14, "base_ghz": 2.6, "turbo_ghz": 5.4}, "gpu": {"model": "RTX 4070", "vram_gb": 8}, "ram_gb": 32, "storage": {"type": "NVMe SSD", "capacity_gb": 1024}, "display": {"size_inches": 17.3, "resolution": "2560x1440", "refresh_hz": 165}}',
        ARRAY['electronics', 'gaming', 'laptop', 'high-performance'],
        'c2eede99-9e2d-4ef8-bb6d-6bb9bd380a33',
        '2024-01-01 00:00:00'
    ),
    (
        'Smart Home Hub',
        '{"brand": "HomeTech", "warranty_years": 2, "voice_assistant": "multiple"}',
        '{"connectivity": ["wifi", "bluetooth", "zigbee", "z-wave"], "compatible_devices": 5000, "voice_assistants": ["alexa", "google", "siri"], "security": {"encryption": "AES-256", "local_processing": true}}',
        ARRAY['smart-home', 'hub', 'iot'],
        'd3eeef99-9f3e-4ef8-bb6d-6bb9bd380a44',
        '2024-01-01 00:00:00'
    );

-- Insert user preferences with JSONB
INSERT INTO user_preferences (user_id, preferences, change_history, updated_at) VALUES
    (
        1,
        '{"theme": "dark", "language": "en", "notifications": {"email": true, "push": true, "sms": false}, "privacy": {"share_data": false, "public_profile": true}, "dashboard": {"layout": "grid", "widgets": ["orders", "wishlist", "recommendations"]}}',
        '{"changes": [{"timestamp": "2024-01-15T10:00:00Z", "field": "theme", "old_value": "light", "new_value": "dark"}, {"timestamp": "2024-02-01T14:30:00Z", "field": "notifications.push", "old_value": false, "new_value": true}]}',
        '2024-02-01 14:30:00'
    ),
    (
        2,
        '{"theme": "light", "language": "es", "notifications": {"email": true, "push": false, "sms": true}, "privacy": {"share_data": true, "public_profile": false}, "dashboard": {"layout": "list", "widgets": ["orders", "reviews"]}}',
        '{"changes": [{"timestamp": "2024-02-20T14:30:00Z", "field": "language", "old_value": "en", "new_value": "es"}]}',
        '2024-02-20 14:30:00'
    ),
    (
        3,
        '{"theme": "auto", "language": "en", "notifications": {"email": false, "push": true, "sms": false}, "privacy": {"share_data": false, "public_profile": false}, "dashboard": {"layout": "compact", "widgets": ["orders"]}}',
        '{"changes": []}',
        '2024-03-10 09:15:00'
    );

-- Insert event logs with JSON payload
INSERT INTO event_logs (event_type, payload, metadata, affected_entities, occurred_at) VALUES
    (
        'order_placed',
        '{"order_id": 1, "customer_id": 1, "total": 1329.98, "items": [{"product_id": 1, "quantity": 1, "price": 1299.99}, {"product_id": 2, "quantity": 1, "price": 29.99}], "payment_method": "credit_card", "shipping_method": "standard"}',
        '{"ip_address": "192.168.1.100", "user_agent": "Mozilla/5.0", "session_id": "sess_abc123", "marketing_source": "email_campaign"}',
        ARRAY[1, 1, 2],
        '2024-01-20 11:30:00'
    ),
    (
        'product_viewed',
        '{"product_id": 3, "customer_id": 2, "view_duration_seconds": 45, "source_page": "search_results", "search_query": "gaming keyboard"}',
        '{"ip_address": "192.168.1.101", "user_agent": "Chrome/120.0", "session_id": "sess_def456"}',
        ARRAY[2, 3],
        '2024-02-24 13:15:00'
    ),
    (
        'inventory_updated',
        '{"product_id": 5, "old_quantity": 30, "new_quantity": 29, "reason": "order_fulfilled", "order_id": 3}',
        '{"warehouse_id": "WH-001", "updated_by": "system", "batch_id": "batch_789"}',
        ARRAY[5],
        '2024-02-25 14:25:00'
    ),
    (
        'user_registered',
        '{"user_id": 4, "email": "david.brown@example.com", "registration_method": "google_oauth", "marketing_consent": true}',
        '{"ip_address": "192.168.1.102", "referral_code": "FRIEND2024", "campaign": "spring_promo"}',
        ARRAY[4],
        '2024-04-05 16:45:00'
    );

-- Insert locations with arrays and JSONB
INSERT INTO locations (name, coordinates, address, nearby_location_ids) VALUES
    (
        'New York Warehouse',
        ARRAY[40.7128, -74.0060],
        '{"street": "123 Industrial Blvd", "city": "Brooklyn", "state": "NY", "zip": "11201", "country": "USA", "building_type": "warehouse", "square_feet": 50000}',
        ARRAY[2, 5]
    ),
    (
        'San Francisco Warehouse',
        ARRAY[37.7749, -122.4194],
        '{"street": "456 Tech Drive", "city": "San Francisco", "state": "CA", "zip": "94102", "country": "USA", "building_type": "warehouse", "square_feet": 35000}',
        ARRAY[1, 3]
    ),
    (
        'Austin Distribution Center',
        ARRAY[30.2672, -97.7431],
        '{"street": "789 Commerce Way", "city": "Austin", "state": "TX", "zip": "78701", "country": "USA", "building_type": "distribution_center", "square_feet": 75000}',
        ARRAY[2, 4]
    ),
    (
        'Seattle Fulfillment Center',
        ARRAY[47.6062, -122.3321],
        '{"street": "321 Logistics Lane", "city": "Seattle", "state": "WA", "zip": "98101", "country": "USA", "building_type": "fulfillment_center", "square_feet": 100000}',
        ARRAY[3, 2]
    ),
    (
        'Boston Store',
        ARRAY[42.3601, -71.0589],
        '{"street": "555 Main Street", "city": "Boston", "state": "MA", "zip": "02101", "country": "USA", "building_type": "retail_store", "square_feet": 5000}',
        ARRAY[1]
    );

-- Insert advanced products with complex types
INSERT INTO advanced_products (sku, name, pricing_rules, categories, compatible_with, inventory_details, image_urls, active) VALUES
    (
        'f47ac10b-58cc-4372-a567-0e02b2c3d479',
        'Premium Subscription Bundle',
        '{"base_price": 99.99, "currency": "USD", "discounts": [{"type": "volume", "min_quantity": 5, "percent_off": 10}, {"type": "loyalty", "member_tier": "gold", "percent_off": 15}], "regional_pricing": {"EU": 89.99, "UK": 79.99, "JP": 10999}}',
        ARRAY['subscription', 'bundle', 'digital'],
        ARRAY[1, 2, 3],
        '{"warehouses": [{"id": "WH-001", "stock": 0, "reserved": 0}], "digital": true, "unlimited": true, "restock_date": null}',
        ARRAY['https://cdn.example.com/bundle-hero.jpg', 'https://cdn.example.com/bundle-features.jpg'],
        true
    ),
    (
        'e58bd21c-69dd-5483-b678-1f13c3d4e580',
        'Ultra-Wide Monitor 49"',
        '{"base_price": 1299.99, "currency": "USD", "cost": 800.00, "margin_percent": 38.46, "dynamic_pricing": {"peak_hours": {"enabled": true, "multiplier": 1.1}, "low_stock": {"threshold": 5, "multiplier": 1.15}}, "bundle_pricing": {"with_desk_mount": 1399.99, "with_hdmi_cable": 1314.99}}',
        ARRAY['electronics', 'monitors', 'gaming', 'professional'],
        ARRAY[4, 5, 6],
        '{"warehouses": [{"id": "WH-001", "stock": 8, "reserved": 2}, {"id": "WH-002", "stock": 12, "reserved": 0}], "digital": false, "restock_date": "2024-06-01", "supplier": "DisplayTech Inc", "lead_time_days": 14}',
        ARRAY['https://cdn.example.com/monitor-front.jpg', 'https://cdn.example.com/monitor-side.jpg', 'https://cdn.example.com/monitor-back.jpg', 'https://cdn.example.com/monitor-setup.jpg'],
        true
    ),
    (
        'e69ce32d-70ee-6594-c789-2e24d4e5f691',
        'Ergonomic Mouse Pad XL',
        '{"base_price": 34.99, "currency": "USD", "cost": 12.00, "margin_percent": 65.7, "promotional": {"active": true, "end_date": "2024-12-31", "sale_price": 24.99}}',
        ARRAY['accessories', 'ergonomic', 'desk'],
        ARRAY[2, 3],
        '{"warehouses": [{"id": "WH-001", "stock": 150, "reserved": 5}, {"id": "WH-002", "stock": 200, "reserved": 10}], "digital": false, "restock_date": null, "supplier": "ComfortTech", "lead_time_days": 7}',
        ARRAY['https://cdn.example.com/mousepad-top.jpg', 'https://cdn.example.com/mousepad-detail.jpg'],
        true
    );

-- ============================================================================
-- User-Defined Types Data (ENUMs, Composite Types, Domains, Ranges)
-- ============================================================================

-- Insert orders with ENUM types
INSERT INTO orders_with_enums (order_number, status, priority, customer_name, order_date, notes) VALUES
    ('ORD-2024-001', 'confirmed', 'high', 'Alice Johnson', '2024-01-15 10:00:00', 'Express shipping requested'),
    ('ORD-2024-002', 'shipped', 'medium', 'Bob Smith', '2024-01-20 14:30:00', NULL),
    ('ORD-2024-003', 'delivered', 'low', 'Carol White', '2024-02-01 09:15:00', 'Left at front door'),
    ('ORD-2024-004', 'pending', 'urgent', 'David Brown', '2024-02-15 16:45:00', 'Customer requested callback'),
    ('ORD-2024-005', 'cancelled', 'medium', 'Eve Davis', '2024-02-20 11:20:00', 'Customer changed mind'),
    ('ORD-2024-006', 'draft', 'critical', 'Frank Miller', '2024-03-01 08:00:00', 'Waiting for payment confirmation'),
    ('ORD-2024-007', 'refunded', 'high', 'Grace Lee', '2024-03-10 13:45:00', 'Product defective');

-- Insert customers with composite types and domains
INSERT INTO customers_with_composite_types (name, email, shipping_address, billing_address, contact, birth_year) VALUES
    (
        'Alice Johnson',
        'alice.johnson@example.com',
        ROW('123 Main St', 'New York', 'NY', '10001', 'USA'),
        ROW('123 Main St', 'New York', 'NY', '10001', 'USA'),
        ROW('555-0101', 'alice.j@example.com', 'email'),
        1985
    ),
    (
        'Bob Smith',
        'bob.smith@techcorp.com',
        ROW('456 Oak Ave', 'San Francisco', 'CA', '94102', 'USA'),
        ROW('789 Corporate Blvd', 'San Francisco', 'CA', '94103', 'USA'),
        ROW('555-0102', 'bob.smith@techcorp.com', 'phone'),
        1990
    ),
    (
        'Carol White',
        'carol.white@email.com',
        ROW('789 Pine Rd', 'Austin', 'TX', '78701', 'USA'),
        ROW('789 Pine Rd', 'Austin', 'TX', '78701', 'USA'),
        ROW('555-0103', 'carol.w@email.com', 'email'),
        1978
    ),
    (
        'David Brown',
        'david.brown@company.org',
        ROW('321 Elm St', 'Seattle', 'WA', '98101', 'USA'),
        ROW('321 Elm St', 'Seattle', 'WA', '98101', 'USA'),
        ROW('555-0104', 'david.brown@company.org', 'phone'),
        1995
    );

-- Insert products with domain and range types
INSERT INTO products_with_domain_types (
    name,
    minimum_order_quantity,
    maximum_order_quantity,
    price,
    wholesale_price_range,
    status,
    contact_email,
    release_year
) VALUES
    (
        'Enterprise Software License',
        5,
        1000,
        ROW(999.99, 'USD'),
        '[800.0,950.0)'::price_range,
        'confirmed',
        'sales@enterprise.com',
        2024
    ),
    (
        'Industrial Equipment Part',
        10,
        500,
        ROW(249.50, 'USD'),
        '[200.0,240.0)'::price_range,
        'shipped',
        'parts@industrial.com',
        2023
    ),
    (
        'Bulk Office Supplies',
        50,
        10000,
        ROW(12.99, 'USD'),
        '[10.0,12.0)'::price_range,
        'delivered',
        'orders@supplies.com',
        2024
    ),
    (
        'Custom Manufacturing Tool',
        1,
        50,
        ROW(1599.99, 'EUR'),
        '[1400.0,1550.0)'::price_range,
        'draft',
        'custom@manufacturing.eu',
        2024
    ),
    (
        'Wholesale Electronics Bundle',
        25,
        2500,
        ROW(89.99, 'USD'),
        '[75.0,85.0)'::price_range,
        'pending',
        'wholesale@electronics.com',
        2023
    );

-- Insert support tickets with ENUMs, domains, and composite types
INSERT INTO support_tickets (
    ticket_number,
    priority,
    status,
    customer_email,
    customer_contact,
    assigned_to_email,
    response_time_hours,
    created_at,
    updated_at
) VALUES
    (
        'TKT-2024-0001',
        'urgent',
        'pending',
        'alice.johnson@example.com',
        ROW('555-0101', 'alice.johnson@example.com', 'email'),
        'support1@company.com',
        2,
        '2024-01-15 09:00:00',
        '2024-01-15 09:30:00'
    ),
    (
        'TKT-2024-0002',
        'high',
        'confirmed',
        'bob.smith@techcorp.com',
        ROW('555-0102', 'bob.smith@techcorp.com', 'phone'),
        'support2@company.com',
        4,
        '2024-01-16 10:15:00',
        '2024-01-16 14:20:00'
    ),
    (
        'TKT-2024-0003',
        'medium',
        'shipped',
        'carol.white@email.com',
        ROW('555-0103', 'carol.white@email.com', 'email'),
        'support1@company.com',
        8,
        '2024-01-18 13:30:00',
        '2024-01-19 09:00:00'
    ),
    (
        'TKT-2024-0004',
        'critical',
        'confirmed',
        'david.brown@company.org',
        ROW('555-0104', 'david.brown@company.org', 'phone'),
        'support3@company.com',
        1,
        '2024-01-20 08:00:00',
        '2024-01-20 08:15:00'
    ),
    (
        'TKT-2024-0005',
        'low',
        'delivered',
        'user5@example.com',
        ROW('555-0105', 'user5@example.com', 'email'),
        'support2@company.com',
        24,
        '2024-01-22 11:00:00',
        '2024-01-23 15:30:00'
    ),
    (
        'TKT-2024-0006',
        'medium',
        'cancelled',
        'user6@example.com',
        ROW('555-0106', 'user6@example.com', 'phone'),
        'support1@company.com',
        6,
        '2024-01-25 14:00:00',
        '2024-01-25 20:00:00'
    );
