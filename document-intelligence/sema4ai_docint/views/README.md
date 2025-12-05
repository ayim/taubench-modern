# document-views

A library for generating SQL views from document extraction data.

## First time setup

Make sure your local virtualenv is set up

```shell
$ uv sync
```

Create a `.env` file with necessary environment variables:

```
SEMA4AI_LOG_LEVEL=INFO
```

The library uses python-dotenv to load these environment variables automatically.

## Usage

The library provides functionality to generate SQL views for document schema data using JSON path notation:

```python
from sema4ai_docint.views import ViewGenerator, BusinessSchema, SchemaField, DataFormat

# Create a view generator with default settings
# - table_name: "docs" (the table containing your JSON documents)
# - document_column: "doc" (the column containing the JSON data)
# - datasource_name: "local_datasource" (the datasource name)
# - project_name: "mindsdb" (mindsdb project name)
view_generator = ViewGenerator()

# Or customize the table and column names
view_generator = ViewGenerator(
    table_name="my_documents",
    document_column="json_data",
    datasource_name="my_datasource",
    project_name="my_project"
)

# Define your business schema using dataclasses with the format field
business_schema = BusinessSchema(fields=[
    SchemaField(
        path="customer.id",
        name="CUSTOMER_ID",
        format=DataFormat(type="string", attributes={"length": 50})
    ),
    SchemaField(
        path="customer.name",
        name="CUSTOMER_NAME",
        format=DataFormat(type="string")
    ),
    SchemaField(
        path="orders[].id",
        name="ORDER_ID",
        format=DataFormat(type="string")
    ),
    SchemaField(
        path="orders[].date",
        name="ORDER_DATE",
        format=DataFormat(type="date")
    ),
    SchemaField(
        path="orders[].items[].sku",
        name="ITEM_SKU",
        format=DataFormat(type="string")
    ),
    SchemaField(
        path="orders[].items[].name",
        name="ITEM_NAME",
        format=DataFormat(type="string")
    ),
    SchemaField(
        path="orders[].items[].qty",
        name="ITEM_QUANTITY",
        format=DataFormat(type="integer")
    ),
    SchemaField(
        path="orders[].items[].price",
        name="ITEM_PRICE",
        format=DataFormat(type="number", attributes={"precision": 10, "scale": 2})
    ),
    SchemaField(
        path="payments[].id",
        name="PAYMENT_ID",
        format=DataFormat(type="string")
    ),
    SchemaField(
        path="payments[].order_id",
        name="PAYMENT_ORDER_ID",
        format=DataFormat(type="string")
    ),
    SchemaField(
        path="payments[].amount",
        name="PAYMENT_AMOUNT",
        format=DataFormat(type="number")
    ),
    SchemaField(
        path="payments[].method",
        name="PAYMENT_METHOD",
        format=DataFormat(type="string")
    )
])

# You can also create from a list of dictionaries with the format field
schema_data = [
    {
        "path": "customer.id",
        "name": "CUSTOMER_ID",
        "format": {"type": "string", "attributes": {"length": 50}}
    },
    {
        "path": "customer.name",
        "name": "CUSTOMER_NAME",
        "format": "string"  # Shorthand for format with just type
    },
    # ... more fields ...
]
business_schema = BusinessSchema.from_dict(schema_data)

# Generate SQL views
views_dict = view_generator.generate_views(business_schema)

# Access views by name
print(views_dict["orders_view"])  # View for orders
print(views_dict["payments_view"])  # View for payments

# Or iterate through all views
for view_name, sql in views_dict.items():
    print(f"View name: {view_name}")
    print(f"SQL: {sql}")
```

### JSON Path Notation

The business schema uses a simplified JSON path notation:

- Use dot notation for nested objects: `customer.name`
- Use `[]` to indicate arrays: `orders[]`
- Combine them for nested arrays: `orders[].items[].price`

Each path in the business schema should include:

- `path`: The JSON path to the data
- `name`: The column name to use in the view
- `format`: Data format specification containing type and optional attributes

### Abstract Type System

The library uses an abstract type system that can be mapped to database-specific types:

```json
{
  "path": "customer.id",
  "name": "CUSTOMER_ID",
  "format": {
    "type": "string",
    "attributes": { "length": 50 }
  }
}
```

Or with shorthand for simple types:

```json
{
  "path": "orders.total",
  "name": "ORDER_TOTAL",
  "format": "number"
}
```

Standard abstract types:

- `string`: For text values (maps to `text` or `varchar` depending on attributes)
- `number`: For decimal numbers (maps to `numeric` or `decimal` depending on attributes)
- `integer`: For whole numbers
- `boolean`: For true/false values
- `date`: For date values
- `datetime`: For date and time values

Type attributes:

- For `string` types:
  - `length`: Maximum string length (e.g., `{"length": 50}`)
- For `number` types:
  - `precision`: Total number of digits (e.g., `{"precision": 10}`)
  - `scale`: Number of decimal places (e.g., `{"precision": 10, "scale": 2}`)

### Database Adapters

The library supports multiple database systems through adapters. Currently, PostgreSQL is supported:

```python
from sema4ai_docint.views import ViewGenerator, PostgresAdapter

# Use the default PostgreSQL adapter
generator = ViewGenerator()

# Or explicitly specify the adapter
postgres_adapter = PostgresAdapter()
generator = ViewGenerator(db_adapter=postgres_adapter)
```

### Example Generated Views

With the schema above, the library would generate these views:

**orders_view**:

```sql
CREATE VIEW mindsdb.orders_view AS (
SELECT
    docs.id AS DOCUMENT_ID,
    CAST(doc->'customer'->>'id' AS VARCHAR(50)) AS CUSTOMER_ID,
    CAST(doc->'customer'->>'name' AS VARCHAR) AS CUSTOMER_NAME,
    CAST(json_array_elements(doc->'orders')->>'id' AS VARCHAR) AS ORDER_ID,
    CAST(json_array_elements(doc->'orders')->>'date' AS DATE) AS ORDER_DATE,
    CAST(json_array_elements(json_array_elements(doc->'orders')->'items')->>'sku' AS VARCHAR) AS ITEM_SKU,
    CAST(json_array_elements(json_array_elements(doc->'orders')->'items')->>'name' AS VARCHAR) AS ITEM_NAME,
    CAST(json_array_elements(json_array_elements(doc->'orders')->'items')->>'qty' AS INT) AS ITEM_QUANTITY,
    CAST(json_array_elements(json_array_elements(doc->'orders')->'items')->>'price' AS DECIMAL(10,2)) AS ITEM_PRICE
FROM
    local_datasource.docs AS docs
);
```

**payments_view**:

```sql
CREATE VIEW mindsdb.payments_view AS (
SELECT
    docs.id AS DOCUMENT_ID,
    CAST(doc->'customer'->>'id' AS VARCHAR(50)) AS CUSTOMER_ID,
    CAST(doc->'customer'->>'name' AS VARCHAR) AS CUSTOMER_NAME,
    CAST(json_array_elements(doc->'payments')->>'id' AS VARCHAR) AS PAYMENT_ID,
    CAST(json_array_elements(doc->'payments')->>'order_id' AS VARCHAR) AS PAYMENT_ORDER_ID,
    CAST(json_array_elements(doc->'payments')->>'amount' AS DECIMAL) AS PAYMENT_AMOUNT,
    CAST(json_array_elements(doc->'payments')->>'method' AS VARCHAR) AS PAYMENT_METHOD
FROM
    local_datasource.docs AS docs
);
```

### View Generation Details

The library generates views with the following characteristics:

1. Views are created in the project schema (default: `mindsdb`)
2. The source table is referenced using the datasource schema (default: `local_datasource`)
3. Array fields are handled using `json_array_elements` function
4. Nested arrays use multiple `json_array_elements` calls
5. All fields are properly cast to their specified types
6. The document ID is included as `DOCUMENT_ID` for reference

You can customize the schema names when creating the view generator:

```python
# Use custom schema names
view_generator = ViewGenerator(
    table_name="docs",
    document_column="doc",
    datasource_name="my_datasource",  # Custom datasource schema
    project_name="my_project"         # Custom project schema
)
```

### Extracted Document

The views are designed to work with extracted documents like this:

```json
{
  "customer": {
    "id": "C123",
    "name": "John Doe",
    "email": "john@example.com"
  },
  "orders": [
    {
      "id": "O456",
      "date": "2023-05-15",
      "items": [
        { "sku": "PROD-A", "name": "Product A", "qty": 2, "price": 19.99 },
        { "sku": "PROD-B", "name": "Product B", "qty": 1, "price": 29.99 }
      ]
    },
    {
      "id": "O789",
      "date": "2023-06-20",
      "items": [{ "sku": "PROD-C", "name": "Product C", "qty": 3, "price": 15.99 }]
    }
  ],
  "payments": [
    {
      "id": "P001",
      "order_id": "O456",
      "amount": 69.97,
      "method": "credit_card",
      "date": "2023-05-15"
    },
    {
      "id": "P002",
      "order_id": "O789",
      "amount": 47.97,
      "method": "paypal",
      "date": "2023-06-20"
    }
  ]
}
```

## Extensibility

### Adding Support for New Databases

To add support for a new database system, create a new adapter that implements the `DBAdapter` interface:

```python
from sema4ai_docint.views import DBAdapter

class SnowflakeAdapter(DBAdapter):
    """
    Adapter for Snowflake database.
    """

    def build_json_path(self, component, is_last, current_path):
        # Implement Snowflake JSON path syntax

    def build_array_accessor(self, current_path, component):
        # Implement Snowflake array access

    def build_lateral_join(self, array_path, alias):
        # Implement Snowflake LATERAL join equivalent

    def apply_type_cast(self, json_path, field_type, attributes=None):
        # Implement Snowflake type casting
```

Then use your custom adapter:

```python
from sema4ai_docint.views import ViewGenerator
from my_package import SnowflakeAdapter

snowflake_adapter = SnowflakeAdapter()
generator = ViewGenerator(db_adapter=snowflake_adapter)
```

## Tests

```shell
$ make test
```

or simply

```shell
$ uv run pytest
```

### Integration Tests

The project includes integration tests that use [testcontainers-python](https://testcontainers-python.readthedocs.io/) to spin up a PostgreSQL database in a Docker container. These tests verify that the generated SQL views work correctly with real data in a PostgreSQL database.

To run the integration tests, you'll need:

1. Docker installed and running on your machine
2. The development dependencies installed

Then run:

```shell
$ uv run pytest
```

The integration tests will:

1. Start a PostgreSQL container
2. Create test tables with sample JSON documents
3. Generate and execute SQL views using our library
4. Verify that the views return the expected data

This provides end-to-end validation that the generated views work correctly in a real database environment.
