-- Edge Cases Test Schema for Snowflake Semantic Data Models
-- Simplified to test core Snowflake-specific types: VARIANT, ARRAY, OBJECT
-- Note: All identifiers are quoted to preserve lowercase names
-- ============================================================================
-- VARIANT - Semi-structured data (Snowflake's most important feature)
-- ============================================================================
CREATE TABLE "products_with_variant" (
  "id" INTEGER AUTOINCREMENT PRIMARY KEY,
  "name" VARCHAR(200) NOT NULL,
  "metadata" VARIANT,
  "specifications" VARIANT
);
CREATE TABLE "events_with_variant" (
  "id" INTEGER AUTOINCREMENT PRIMARY KEY,
  "event_type" VARCHAR(50) NOT NULL,
  "payload" VARIANT NOT NULL
);
-- ============================================================================
-- ARRAY - Snowflake arrays
-- ============================================================================
CREATE TABLE "products_with_arrays" (
  "id" INTEGER AUTOINCREMENT PRIMARY KEY,
  "name" VARCHAR(200) NOT NULL,
  "tags" ARRAY,
  "category_ids" ARRAY
);
-- ============================================================================
-- OBJECT - Structured objects
-- ============================================================================
CREATE TABLE "customers_with_objects" (
  "id" INTEGER AUTOINCREMENT PRIMARY KEY,
  "name" VARCHAR(100) NOT NULL,
  "email" VARCHAR(255) NOT NULL,
  "address" OBJECT,
  "contact_info" OBJECT
);
-- Comments
COMMENT ON TABLE "products_with_variant" IS 'Products with VARIANT metadata';
COMMENT ON TABLE "events_with_variant" IS 'Events with VARIANT payloads';
COMMENT ON TABLE "products_with_arrays" IS 'Products with ARRAY types';
COMMENT ON TABLE "customers_with_objects" IS 'Customers with OBJECT types';