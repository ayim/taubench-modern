-- Edge Cases Test Schema for Postgres Semantic Data Models
-- This file contains tables with special PostgreSQL data types that have caused issues

-- Products with metadata stored as JSON
CREATE TABLE products_with_json (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    -- JSON column for flexible metadata
    metadata JSON,
    -- JSONB column for optimized querying
    specifications JSONB,
    -- Array column for tags
    tags TEXT[],
    -- UUID column for external references
    external_id UUID DEFAULT gen_random_uuid(),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User preferences with JSONB configuration
CREATE TABLE user_preferences (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    -- JSONB for nested configuration objects
    preferences JSONB NOT NULL DEFAULT '{}',
    -- JSON for audit history
    change_history JSON,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Events log with JSON payload
CREATE TABLE event_logs (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    -- JSON payload for event data
    payload JSON NOT NULL,
    -- JSONB for indexed metadata
    metadata JSONB,
    -- Array of affected entity IDs
    affected_entities INTEGER[],
    occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Geo locations with array types
CREATE TABLE locations (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    -- Array of coordinates [latitude, longitude]
    coordinates NUMERIC[],
    -- JSONB for detailed address
    address JSONB,
    -- Array of nearby location IDs
    nearby_location_ids INTEGER[]
);

-- Products with advanced types
CREATE TABLE advanced_products (
    id SERIAL PRIMARY KEY,
    sku UUID DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    -- JSONB for complex pricing structures
    pricing_rules JSONB,
    -- Array for multiple categories
    categories TEXT[],
    -- Array for compatible product IDs
    compatible_with INTEGER[],
    -- JSONB for inventory tracking
    inventory_details JSONB,
    -- Array for images
    image_urls TEXT[],
    active BOOLEAN DEFAULT true
);

-- Create indexes on JSONB columns for better query performance
CREATE INDEX idx_products_with_json_specifications ON products_with_json USING GIN (specifications);
CREATE INDEX idx_user_preferences_preferences ON user_preferences USING GIN (preferences);
CREATE INDEX idx_event_logs_metadata ON event_logs USING GIN (metadata);
CREATE INDEX idx_locations_address ON locations USING GIN (address);
CREATE INDEX idx_advanced_products_pricing ON advanced_products USING GIN (pricing_rules);

-- Comments for documentation
COMMENT ON TABLE products_with_json IS 'Products with JSON/JSONB metadata for flexible attributes';
COMMENT ON TABLE user_preferences IS 'User preferences stored as JSONB for complex configurations';
COMMENT ON TABLE event_logs IS 'Event logs with JSON payloads for audit trails';
COMMENT ON TABLE locations IS 'Geographic locations with array-based coordinates';
COMMENT ON TABLE advanced_products IS 'Products with advanced PostgreSQL types including UUID and arrays';

COMMENT ON COLUMN products_with_json.metadata IS 'Flexible JSON metadata for product attributes';
COMMENT ON COLUMN products_with_json.specifications IS 'JSONB specifications for optimized querying';
COMMENT ON COLUMN products_with_json.tags IS 'Array of tags for categorization';
COMMENT ON COLUMN user_preferences.preferences IS 'JSONB user preferences with nested structure';
COMMENT ON COLUMN event_logs.payload IS 'JSON payload containing event details';
COMMENT ON COLUMN locations.coordinates IS 'Array of numeric coordinates [lat, lon]';
COMMENT ON COLUMN advanced_products.pricing_rules IS 'JSONB pricing rules with complex conditions';

-- ============================================================================
-- User-Defined Types (ENUMs, Composite Types, Domains, Ranges)
-- ============================================================================

-- ENUM type for order status
CREATE TYPE order_status_enum AS ENUM ('draft', 'pending', 'confirmed', 'shipped', 'delivered', 'cancelled', 'refunded');

-- ENUM type for priority levels
CREATE TYPE priority_level AS ENUM ('low', 'medium', 'high', 'urgent', 'critical');

-- Composite type for address
CREATE TYPE address_type AS (
    street VARCHAR(200),
    city VARCHAR(100),
    state VARCHAR(50),
    postal_code VARCHAR(20),
    country VARCHAR(100)
);

-- Composite type for money with currency
CREATE TYPE money_with_currency AS (
    amount NUMERIC(10, 2),
    currency_code CHAR(3)
);

-- Composite type for contact information
CREATE TYPE contact_info AS (
    phone VARCHAR(20),
    email VARCHAR(100),
    preferred_method VARCHAR(20)
);

-- Domain type for positive integers
CREATE DOMAIN positive_int AS INTEGER CHECK (VALUE > 0);

-- Domain type for email addresses (basic validation)
CREATE DOMAIN email_address AS VARCHAR(255) CHECK (VALUE ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$');

-- Domain type for year values
CREATE DOMAIN year_value AS INTEGER CHECK (VALUE >= 1900 AND VALUE <= 2100);

-- Custom range type for price ranges (using float8 subtype for simplicity)
CREATE TYPE price_range AS RANGE (
    subtype = float8,
    subtype_diff = float8mi
);

-- Orders with ENUM types
CREATE TABLE orders_with_enums (
    id SERIAL PRIMARY KEY,
    order_number VARCHAR(50) NOT NULL UNIQUE,
    status order_status_enum NOT NULL DEFAULT 'draft',
    priority priority_level NOT NULL DEFAULT 'medium',
    customer_name VARCHAR(100) NOT NULL,
    order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);

-- Customers with composite types and domains
CREATE TABLE customers_with_composite_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email email_address NOT NULL UNIQUE,
    shipping_address address_type,
    billing_address address_type,
    contact contact_info,
    birth_year year_value,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Products with domain and range types
CREATE TABLE products_with_domain_types (
    id SERIAL PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    minimum_order_quantity positive_int DEFAULT 1,
    maximum_order_quantity positive_int DEFAULT 100,
    price money_with_currency NOT NULL,
    wholesale_price_range price_range,
    status order_status_enum DEFAULT 'draft',
    contact_email email_address,
    release_year year_value
);

-- Tickets/Support system with ENUMs and composite types
CREATE TABLE support_tickets (
    id SERIAL PRIMARY KEY,
    ticket_number VARCHAR(50) NOT NULL UNIQUE,
    priority priority_level NOT NULL DEFAULT 'medium',
    status order_status_enum NOT NULL DEFAULT 'pending',
    customer_email email_address NOT NULL,
    customer_contact contact_info,
    assigned_to_email email_address,
    response_time_hours positive_int,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_orders_with_enums_status ON orders_with_enums(status);
CREATE INDEX idx_orders_with_enums_priority ON orders_with_enums(priority);
CREATE INDEX idx_products_with_domain_status ON products_with_domain_types(status);
CREATE INDEX idx_support_tickets_priority ON support_tickets(priority);
CREATE INDEX idx_support_tickets_status ON support_tickets(status);

-- Comments for documentation
COMMENT ON TABLE orders_with_enums IS 'Orders using ENUM types for status and priority';
COMMENT ON TABLE customers_with_composite_types IS 'Customers using composite types for addresses and contact info';
COMMENT ON TABLE products_with_domain_types IS 'Products using domain types for validation and range types for pricing';
COMMENT ON TABLE support_tickets IS 'Support tickets combining ENUMs, domains, and composite types';

COMMENT ON COLUMN orders_with_enums.status IS 'Order status using custom ENUM type';
COMMENT ON COLUMN orders_with_enums.priority IS 'Priority level using custom ENUM type';
COMMENT ON COLUMN customers_with_composite_types.email IS 'Email validated using domain type';
COMMENT ON COLUMN customers_with_composite_types.shipping_address IS 'Shipping address using composite type';
COMMENT ON COLUMN customers_with_composite_types.contact IS 'Contact information using composite type';
COMMENT ON COLUMN products_with_domain_types.minimum_order_quantity IS 'Minimum order quantity using positive_int domain';
COMMENT ON COLUMN products_with_domain_types.price IS 'Price with currency using composite type';
COMMENT ON COLUMN products_with_domain_types.wholesale_price_range IS 'Wholesale price range using custom range type';
COMMENT ON COLUMN support_tickets.response_time_hours IS 'Response time in hours using positive_int domain';

