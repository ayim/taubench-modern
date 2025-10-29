# Snowflake Test Resources

SQL files for Snowflake-specific semantic data model testing.

## Files

- **schema.sql**: E-commerce schema with quoted identifiers (preserves lowercase names)
- **data.sql**: Test data with quoted table/column names
- **edge_cases_schema.sql**: Snowflake-specific data types (VARIANT, ARRAY, OBJECT)
- **edge_cases_data.sql**: Test data for edge cases

## Snowflake-Specific Types Tested

Focus on the three most important Snowflake-specific types:

- **VARIANT**: Semi-structured data (JSON, XML, Avro, Parquet) - Snowflake's key differentiator
- **ARRAY**: Snowflake arrays (different syntax from PostgreSQL)
- **OBJECT**: Structured objects (similar to composite types)

## Notes

All identifiers are quoted to maintain lowercase names (Snowflake converts unquoted to UPPERCASE).
