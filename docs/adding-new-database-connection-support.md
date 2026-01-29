# Adding New Database Connection Support

This document provides a comprehensive guide for adding support for new database engines (like BigQuery, MySQL, etc.) to the agent platform. Currently, PostgreSQL and Snowflake have been fully tested end-to-end for semantic data model creation.

## Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Implementation Steps](#implementation-steps)
4. [Testing Requirements](#testing-requirements)
5. [Deployment Considerations](#deployment-considerations)
6. [Example: Adding BigQuery Support](#example-adding-bigquery-support)

---

## Overview

Adding a new database connection involves changes across multiple layers of the platform:

1. **Core Layer**: Define configuration schemas and data structures
2. **Server Layer**: Implement Ibis connection logic and inspection
3. **API Layer**: Expose endpoints and handle requests
4. **UI Layer**: Add forms and icons for the new connection type
5. **Testing Layer**: Create comprehensive tests including semantic data models
6. **Documentation Layer**: Update documentation and examples

### Architecture Components

```
┌─────────────────────────────────────────────────────────────┐
│                         Frontend UI                          │
│  (Data Connection Forms, Icons, Selection UI)               │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ├─ @sema4ai/data-interface (schemas)
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                    FastAPI REST Endpoints                     │
│            (data_connections.py API routes)                   │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│             DataConnectionInspector (Kernel)                  │
│  - Creates Ibis connections                                   │
│  - Inspects tables/columns                                    │
│  - Validates semantic data models                             │
└──────────────────────────────┬──────────────────────────────┘
                               │
┌──────────────────────────────▼──────────────────────────────┐
│                  Ibis Framework (Backend)                     │
│  - Database-specific drivers                                  │
│  - Query execution                                            │
│  - Schema introspection                                       │
└───────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

Before adding a new database engine, ensure:

1. **Ibis Support**: The database must be supported by the [Ibis framework](https://ibis-project.org/backends/). Check the [Ibis backends documentation](https://ibis-project.org/backends/) for available backends.

2. **Python Drivers**: Required Python database drivers must be available and compatible with Python 3.12+.

3. **Connection Parameters**: Understand the connection parameters required by the database (host, port, credentials, etc.).

4. **Test Environment**: Access to a test instance of the database for development and testing.

5. **Special Considerations**: Research any special requirements or limitations (e.g., Snowflake's Arrow format issues).

---

## Implementation Steps

### Step 1: Core Layer - Define Configuration Schema

**File**: `core/src/agent_platform/core/payloads/data_connection.py`

#### 1.1 Add Configuration Dataclass

```python
@dataclass
class BigqueryDataConnectionConfiguration:
    project_id: str
    dataset: str
    service_account_keys: str | None = None
    service_account_json: str | None = None
```

**Guidelines**:

- Include all required connection parameters
- Use descriptive field names matching the database's terminology
- Add optional fields with `| None = None`
- Consider security implications (passwords, keys, tokens)

#### 1.2 Update DataConnectionEngine Literal

```python
DataConnectionEngine = Literal[
    "postgres",
    "redshift",
    "snowflake",
    # ... other engines ...
    "bigquery",  # Add your new engine here
    "sqlite",
]
```

#### 1.3 Update DataConnectionConfiguration Union

```python
DataConnectionConfiguration = (
    PostgresDataConnectionConfiguration
    | RedshiftDataConnectionConfiguration
    # ... other configurations ...
    | BigqueryDataConnectionConfiguration  # Add your configuration
    | SQLiteDataConnectionConfiguration
)
```

#### 1.4 Add Specific DataConnection Class

```python
@dataclass
class BigqueryDataConnection(BaseDataConnection):
    engine: Literal["bigquery"] = "bigquery"
    configuration: BigqueryDataConnectionConfiguration
```

#### 1.5 Update DataConnection Union Type

```python
DataConnection = (
    PostgresDataConnection
    | RedshiftDataConnection
    # ... other connections ...
    | BigqueryDataConnection  # Add your connection
    | SQLiteDataConnection
)
```

---

### Step 2: Core Layer - Add Configuration Parser

**File**: `core/src/agent_platform/core/data_connections/data_connections.py`

#### 2.1 Add Parser Method

```python
@classmethod
def _parse_bigquery_config(
    cls, config_data: dict[str, Any]
) -> BigqueryDataConnectionConfiguration:
    """Parse BigQuery configuration."""
    return BigqueryDataConnectionConfiguration(**config_data)
```

**Special Cases**:

- If your database needs SSL configuration, use `_parse_ssl_config`:
  ```python
  return cls._parse_ssl_config(config_data, YourDataConnectionConfiguration)
  ```
- For complex authentication (like Snowflake), you may need custom logic:
  ```python
  credential_type = config_data.get("credential_type", "password")
  if credential_type == "custom-key-pair":
      # Handle custom authentication
      pass
  ```

#### 2.2 Register Parser in `_get_engine_parser`

```python
@classmethod
def _get_engine_parser(cls, engine: str):
    """Get the appropriate parser function for the given engine."""
    parsers = {
        "postgres": cls._parse_postgres_config,
        "redshift": cls._parse_redshift_config,
        # ... other parsers ...
        "bigquery": cls._parse_bigquery_config,  # Add your parser
        "sqlite": cls._parse_sqlite_config,
    }
    if engine not in parsers:
        raise ValueError(f"Unsupported engine type: {engine}")
    return parsers[engine]
```

---

### Step 3: Server Layer - Add Dependencies

**File**: `core/pyproject.toml`

#### 3.1 Update Ibis Dependencies

Add the required Ibis backend to the dependencies:

```toml
dependencies = [
    # ... existing dependencies ...
    "ibis-framework[datafusion,duckdb,postgres,snowflake,sqlite,bigquery]>=10.8.0,<11.0.0",
    # Add your backend ──────────────────────────────────────────^
]
```

#### 3.2 Add Database-Specific Drivers (if needed)

Some databases require additional Python packages:

```toml
dependencies = [
    # ... existing dependencies ...
    "google-cloud-bigquery>=3.0.0,<4.0.0",  # Example for BigQuery
]
```

**Common Database Drivers**:

- **PostgreSQL**: `psycopg[binary,pool]>=3.2.2,<4.0.0` (already included)
- **MySQL**: `pymysql>=1.1.0,<2.0.0` or `mysqlclient`
- **Redshift**: Uses PostgreSQL driver (already included)
- **BigQuery**: `google-cloud-bigquery`
- **Oracle**: `oracledb>=2.0.0,<3.0.0`
- **MSSQL**: `pymssql>=2.3.0,<3.0.0` or `pyodbc`

---

### Step 4: Server Layer - Implement Ibis Connection

**File**: `server/src/agent_platform/server/kernel/data_connection_inspector.py`

#### 4.1 Import Configuration Class

```python
if typing.TYPE_CHECKING:
    # ... other imports ...
    from agent_platform.core.payloads.data_connection import (
        # ... other configurations ...
        BigqueryDataConnectionConfiguration,
    )
```

#### 4.2 Add Connection Creation Method

```python
@classmethod
async def _create_bigquery_connection(
    cls, config: "BigqueryDataConnectionConfiguration"
) -> Any:
    """Create BigQuery ibis connection."""
    import time
    import ibis

    initial_time = time.monotonic()
    try:
        ret = ibis.bigquery.connect(
            project_id=config.project_id,
            dataset_id=config.dataset,
            credentials=config.service_account_json,  # Or handle auth differently
        )
        logger.info(
            f"Created ibis.bigquery connection in {time.monotonic() - initial_time:.2f} seconds"
        )
        return ret
    except ConnectionFailedError:
        raise
    except Exception as e:
        error_message = _parse_connection_error(e, "bigquery", config)
        logger.error(
            "Failed to create bigquery connection",
            error=error_message,
            project_id=config.project_id,
            exc_info=True,
        )
        raise ConnectionFailedError(error_message) from e
```

**Important Notes**:

1. Always wrap in try-except with `ConnectionFailedError` handling
2. Use `_parse_connection_error()` for user-friendly error messages
3. Log connection time for performance monitoring
4. Log relevant connection details (but never passwords!)

#### 4.3 Add to `create_ibis_connection` Method

```python
@classmethod
async def create_ibis_connection(cls, data_connection: "DataConnection") -> Any:
    """Create an ibis connection based on the data connection configuration."""
    from agent_platform.core.payloads.data_connection import (
        PostgresDataConnectionConfiguration,
        RedshiftDataConnectionConfiguration,
        SQLiteDataConnectionConfiguration,
        BigqueryDataConnectionConfiguration,  # Add import
    )

    engine = data_connection.engine
    config = data_connection.configuration

    if engine == "sqlite":
        return await cls._create_sqlite_connection(
            typing.cast(SQLiteDataConnectionConfiguration, config)
        )
    # ... other engines ...
    elif engine == "bigquery":
        return await cls._create_bigquery_connection(
            typing.cast(BigqueryDataConnectionConfiguration, config)
        )
    else:
        raise ValueError(f"Unsupported engine for inspection: {engine}")
```

#### 4.4 Handle Backend-Specific Issues

Some databases require special handling. For example, Snowflake has Arrow format issues:

**File**: `server/src/agent_platform/server/utils/<database>_utils.py`

Create a utility file if your database needs special handling:

```python
"""Utility functions for BigQuery-specific operations."""

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pyarrow

def is_bigquery_backend(ibis_expr: Any) -> bool:
    """Check if an ibis expression is backed by a BigQuery connection."""
    try:
        if hasattr(ibis_expr, "_find_backend"):
            backend = ibis_expr._find_backend()
            return hasattr(backend, "name") and backend.name == "bigquery"
        elif hasattr(ibis_expr, "get_backend"):
            backend = ibis_expr.get_backend()
            return hasattr(backend, "name") and backend.name == "bigquery"
        elif hasattr(ibis_expr, "name"):
            return ibis_expr.name == "bigquery"
        return False
    except Exception:
        return False
```

**Reference**: See `server/src/agent_platform/server/utils/snowflake_utils.py` for a complete example.

#### 4.5 Add Error Patterns (Optional)

If your database has specific error messages that need user-friendly translations:

**File**: `server/src/agent_platform/server/kernel/data_connection_inspector.py`

```python
_ERROR_PATTERNS = [
    # ... existing patterns ...

    # BigQuery-specific errors
    _ErrorPattern(
        keywords=["project", "does not exist"],
        message_template=(
            "Project '{project_id}' does not exist or is not accessible. "
            "Please verify the project ID and your permissions."
        ),
        config_fields=["project_id"],
        engine_specific="bigquery",
    ),
    _ErrorPattern(
        keywords=["dataset", "not found"],
        message_template=(
            "Dataset '{dataset}' not found in project '{project_id}'. "
            "Please verify the dataset name."
        ),
        config_fields=["dataset", "project_id"],
        engine_specific="bigquery",
    ),
]
```

---

### Step 5: Testing Layer - Create Test Infrastructure

#### 5.1 Add Test Fixtures

**File**: `server/tests/spar/semantic_data_models/conftest.py`

##### 5.1.1 Update Engine Fixture

```python
@pytest.fixture(scope="module", params=["postgres", "snowflake", "bigquery"])  # Add new engine
def engine(request: pytest.FixtureRequest) -> "DataConnectionEngine":
    """
    Parametrized fixture that provides the database engine to test against.
    """
    engine_name = request.param

    # Skip tests if credentials are not configured
    if engine_name == "bigquery":
        required_env_vars = [
            "BIGQUERY_PROJECT_ID",
            "BIGQUERY_DATASET",
            "BIGQUERY_CREDENTIALS",
        ]
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]

        if missing_vars:
            missing = ", ".join(missing_vars)
            pytest.skip(
                f"BigQuery tests skipped: missing environment variables: {missing}. "
                "Set these environment variables to run BigQuery tests."
            )

    return engine_name
```

##### 5.1.2 Add Configuration Factory

```python
@pytest.fixture(scope="module")
def sdm_seed_data_connection_configuration(
    engine: "DataConnectionEngine",
) -> "DataConnectionConfiguration":
    """Fixture that provides a DataConnectionConfiguration for seeding test data."""
    from dataclasses import fields
    from agent_platform.core.payloads.data_connection import (
        PostgresDataConnectionConfiguration,
        SnowflakeDataConnectionConfiguration,
        BigqueryDataConnectionConfiguration,  # Add import
    )

    match engine:
        case "postgres":
            # ... existing postgres config ...
            pass
        case "snowflake":
            # ... existing snowflake config ...
            pass
        case "bigquery":
            defaults = {
                "project_id": os.getenv("BIGQUERY_PROJECT_ID"),
                "dataset": os.getenv("BIGQUERY_DATASET"),
                "service_account_json": os.getenv("BIGQUERY_CREDENTIALS"),
            }
            # Apply env overrides
            config = {**defaults, **attributes_to_apply}
            return BigqueryDataConnectionConfiguration(**config)
```

##### 5.1.3 Create Database Initialization Function

```python
@contextmanager
def _initialize_bigquery_database(
    config: "BigqueryDataConnectionConfiguration",
    resources_path: Path,
) -> "Generator[str, Any, Any]":
    """
    Initialize a BigQuery dataset for testing.

    This function:
    1. Creates a test dataset
    2. Loads schema DDL from bigquery/schema.sql
    3. Loads test data from shared/data.sql
    4. Yields the dataset name
    5. Cleans up the dataset after tests
    """
    from google.cloud import bigquery
    import json

    # Parse credentials
    credentials_info = json.loads(config.service_account_json)
    client = bigquery.Client.from_service_account_info(credentials_info)

    # Generate unique test dataset name
    dataset_id = f"test_sdm_{uuid.uuid4().hex[:8]}"
    full_dataset_id = f"{config.project_id}.{dataset_id}"

    try:
        # Create dataset
        dataset = bigquery.Dataset(full_dataset_id)
        dataset = client.create_dataset(dataset)
        logger.info(f"Created test dataset: {full_dataset_id}")

        # Load schema and data
        schema_sql, data_sql = _load_sql_files(resources_path, "bigquery")

        # Execute schema DDL
        for statement in schema_sql.split(";"):
            if statement.strip():
                # Adjust SQL for BigQuery syntax if needed
                adjusted_statement = statement.replace("VARCHAR", "STRING")
                client.query(adjusted_statement).result()

        # Execute data DML
        for statement in data_sql.split(";"):
            if statement.strip():
                client.query(statement).result()

        logger.info(f"Loaded schema and data into {full_dataset_id}")

        yield dataset_id

    finally:
        # Cleanup
        client.delete_dataset(full_dataset_id, delete_contents=True, not_found_ok=True)
        logger.info(f"Deleted test dataset: {full_dataset_id}")
```

##### 5.1.4 Update Database Initialization Dispatcher

```python
@pytest.fixture(scope="module")
def initialize_data_base(
    engine: "DataConnectionEngine",
    semantic_data_model_resources_path: Path,
    sdm_seed_data_connection_configuration: "DataConnectionConfiguration",
) -> "Generator[str, Any, Any]":
    """Fixture that initializes a database for the given engine."""
    from agent_platform.core.payloads.data_connection import (
        PostgresDataConnectionConfiguration,
        SnowflakeDataConnectionConfiguration,
        BigqueryDataConnectionConfiguration,  # Add import
    )

    match engine:
        case "postgres":
            assert isinstance(
                sdm_seed_data_connection_configuration, PostgresDataConnectionConfiguration
            )
            ctx = _initialize_postgres_database(
                sdm_seed_data_connection_configuration,
                semantic_data_model_resources_path,
            )
        case "snowflake":
            assert isinstance(
                sdm_seed_data_connection_configuration, SnowflakeDataConnectionConfiguration
            )
            ctx = _initialize_snowflake_database(
                sdm_seed_data_connection_configuration,
                semantic_data_model_resources_path,
            )
        case "bigquery":
            assert isinstance(
                sdm_seed_data_connection_configuration, BigqueryDataConnectionConfiguration
            )
            ctx = _initialize_bigquery_database(
                sdm_seed_data_connection_configuration,
                semantic_data_model_resources_path,
            )
        case _:
            pytest.skip(f"Engine {engine} not yet supported for database initialization")

    with ctx as db_identifier:
        yield db_identifier
```

#### 5.2 Create SQL Schema Files

##### 5.2.1 Schema DDL File

**File**: `server/tests/spar/resources/semantic_data_models/bigquery/schema.sql`

```sql
-- Create tables with BigQuery-specific syntax
CREATE TABLE IF NOT EXISTS customers (
    customer_id INT64,
    name STRING,
    email STRING,
    created_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS orders (
    order_id INT64,
    customer_id INT64,
    order_date DATE,
    total_amount NUMERIC
);

-- Add more tables as needed for comprehensive testing
```

**Guidelines**:

- Use database-specific data types
- Include various data types (strings, numbers, dates, timestamps, etc.)
- Create relationships between tables (foreign keys if supported)
- Include edge cases (nullable columns, default values, etc.)

##### 5.2.2 Data DML File (Optional - can reuse shared)

**File**: `server/tests/spar/resources/semantic_data_models/bigquery/data.sql`

Or reuse the shared data file if SQL is compatible:

**File**: `server/tests/spar/resources/semantic_data_models/shared/data.sql`

```sql
INSERT INTO customers (customer_id, name, email, created_at) VALUES
(1, 'John Doe', 'john@example.com', '2024-01-01 10:00:00'),
(2, 'Jane Smith', 'jane@example.com', '2024-01-02 11:00:00');

INSERT INTO orders (order_id, customer_id, order_date, total_amount) VALUES
(1001, 1, '2024-01-15', 150.00),
(1002, 2, '2024-01-16', 200.00);
```

#### 5.3 Create README for Test Setup

**File**: `server/tests/spar/resources/semantic_data_models/bigquery/README.md`

````markdown
# BigQuery Test Setup

## Prerequisites

1. A Google Cloud Platform account
2. A project with BigQuery API enabled
3. Service account credentials with BigQuery access

## Environment Variables

Set the following environment variables to run BigQuery tests:

```bash
export BIGQUERY_PROJECT_ID="your-project-id"
export BIGQUERY_DATASET="test_dataset"  # Will be created/deleted by tests
export BIGQUERY_CREDENTIALS='{"type": "service_account", ...}'  # JSON string
```
````

## Service Account Permissions

The service account needs:

- `bigquery.datasets.create`
- `bigquery.datasets.delete`
- `bigquery.tables.create`
- `bigquery.tables.getData`
- `bigquery.tables.list`

## Running Tests

```bash
# Run all semantic data model tests (including BigQuery if configured)
make test-unit

# Run specific test
uv run --project agent_platform_server pytest \
  server/tests/spar/semantic_data_models/test_spar_semantic_data_models.py \
  -k bigquery
```

````

---

### Step 6: UI Layer - Add Frontend Support

#### 6.1 Update Data Interface Package

The `@sema4ai/data-interface` package (currently v2.2.3) contains Zod schemas for data connection configurations. This is typically maintained separately.

**Contact the UI/frontend team** to add the new database engine schema to the `@sema4ai/data-interface` package.

The schema should look similar to:

```typescript
// In @sema4ai/data-interface
export const BigqueryDataConnectionConfigurationSchema = z.object({
  project_id: z.string().describe("Google Cloud Project ID"),
  dataset: z.string().describe("BigQuery dataset name"),
  service_account_json: z.string().optional().describe("Service account JSON credentials"),
  service_account_keys: z.string().optional().describe("Service account key file path"),
});

// Add to engine schemas map
export const dataSourceConnectionConfigurationSchemaByEngine = {
  postgres: PostgresDataConnectionConfigurationSchema,
  snowflake: SnowflakeDataConnectionConfigurationSchema,
  // ... other engines ...
  bigquery: BigqueryDataConnectionConfigurationSchema,  // Add here
} as const;

// Add to engine names
export const customerFacingDataSourceEngineName = (engine: DataSourceEngineWithConnection): string => {
  switch (engine) {
    case 'postgres': return 'PostgreSQL';
    case 'snowflake': return 'Snowflake';
    // ... other engines ...
    case 'bigquery': return 'BigQuery';  // Add here
  }
};
````

#### 6.2 Add Database Icon

**File**: `workroom/frontend/src/components/DataConnection/components/DataConnectionIcon.tsx`

```typescript
import { IconBigQuery } from '@sema4ai/icons'; // Ensure icon exists

export const getDataConnectionIcon = (engine: string) => {
  switch (engine) {
    case 'postgres':
      return IconPostgres;
    case 'snowflake':
      return IconSnowflake;
    // ... other engines ...
    case 'bigquery':
      return IconBigQuery; // Add icon
    default:
      return IconDatabase; // Default icon
  }
};
```

**Icon Requirements**:

1. SVG format
2. Consistent size (usually 24x24 or 32x32)
3. Follow Sema4.ai design system
4. Add to `@sema4ai/icons` package

#### 6.3 UI Auto-Updates

Once the `@sema4ai/data-interface` package is updated and the spar-ui dependency is updated to the new version, the following UI components will automatically include the new database engine:

1. **Data Connection Form** - The engine dropdown will include the new option
2. **Data Connection Configuration** - Form fields will be generated from the Zod schema
3. **Data Connection Table** - The engine filter will include the new type
4. **Semantic Data Model** - Data connection selection will show the new engine

---

### Step 7: Documentation Updates

#### 7.1 Update Main Documentation

**File**: `docs/data-connections-integrations-erd.md`

Add the new engine to the supported engines list and document any special configuration requirements.

#### 7.2 Create Connection Guide

Create a new guide or update existing guides:

**File**: `docs/database-connections/<engine>-connection-guide.md`

```markdown
# BigQuery Connection Guide

## Overview

This guide explains how to connect your agent to Google BigQuery.

## Prerequisites

- A Google Cloud Platform account
- A project with BigQuery API enabled
- Service account with appropriate permissions

## Configuration Parameters

### Required

- **Project ID**: Your Google Cloud project ID
- **Dataset**: The BigQuery dataset to access
- **Credentials**: Service account JSON credentials

### Optional

- **Service Account Keys**: Path to service account key file

## Step-by-Step Setup

1. Create a service account in Google Cloud Console
2. Grant BigQuery permissions (bigquery.dataViewer, bigquery.jobUser)
3. Download service account JSON key
4. In Sema4.ai Agent Platform:
   - Navigate to Data Connections
   - Click "Create Connection"
   - Select "BigQuery" as the engine
   - Fill in the required fields
   - Test the connection

## Troubleshooting

### Connection Fails

- Verify project ID is correct
- Ensure service account has necessary permissions
- Check that BigQuery API is enabled in the project

### Cannot Access Dataset

- Verify dataset exists in the project
- Ensure service account has access to the dataset
```

---

## Testing Requirements

### Unit Tests

1. **Connection Creation Tests**

   ```python
   # server/tests/kernel/test_data_connection_inspector.py
   async def test_create_bigquery_connection():
       """Test BigQuery connection creation."""
       config = BigqueryDataConnectionConfiguration(
           project_id="test-project",
           dataset="test_dataset",
       )
       connection = await DataConnectionInspector._create_bigquery_connection(config)
       assert connection is not None
   ```

2. **Configuration Parsing Tests**

   ```python
   # core/tests/data_connections/test_data_connection_parsing.py
   def test_parse_bigquery_config():
       """Test parsing BigQuery configuration."""
       config_data = {
           "project_id": "test-project",
           "dataset": "test_dataset",
       }
       config = DataConnection._parse_bigquery_config(config_data)
       assert isinstance(config, BigqueryDataConnectionConfiguration)
       assert config.project_id == "test-project"
   ```

3. **Error Handling Tests**
   ```python
   # server/tests/kernel/test_data_connection_error_handling.py
   async def test_bigquery_connection_error_handling():
       """Test error handling for invalid BigQuery connections."""
       config = BigqueryDataConnectionConfiguration(
           project_id="invalid-project",
           dataset="invalid_dataset",
       )
       with pytest.raises(ConnectionFailedError) as exc_info:
           await DataConnectionInspector._create_bigquery_connection(config)
       assert "project" in str(exc_info.value).lower()
   ```

### Integration Tests

1. **Database Inspection Tests**

   ```python
   # server/tests/endpoints/test_data_connections_integration_all_types.py
   async def test_inspect_bigquery_connection(bigquery_connection_fixture):
       """Test inspecting a BigQuery data connection."""
       inspector = DataConnectionInspector(
           bigquery_connection_fixture,
           DataConnectionsInspectRequest(inspect_columns=True, n_sample_rows=5)
       )
       result = await inspector.inspect_connection()
       assert len(result.tables) > 0
       assert all(len(table.columns) > 0 for table in result.tables)
   ```

2. **Semantic Data Model Tests**
   ```python
   # server/tests/spar/semantic_data_models/test_spar_semantic_data_models.py
   # These tests run automatically for all engines in the fixture params
   async def test_semantic_data_model_validation(engine, sdm_data_connection):
       """Test semantic data model validation."""
       # This test will run for postgres, snowflake, AND bigquery
       validator = SemanticDataModelValidator(
           semantic_data_model,
           thread_id=None,
           storage=storage,
           user=user,
       )
       result = await validator.validate()
       assert validator.is_valid
   ```

### End-to-End Tests

1. **API Endpoint Tests**
   ```python
   # server/tests/endpoints/test_data_connections_endpoint.py
   async def test_create_bigquery_connection_via_api(client, auth_headers):
       """Test creating BigQuery connection via API."""
       payload = {
           "name": "Test BigQuery",
           "description": "Test connection",
           "engine": "bigquery",
           "configuration": {
               "project_id": "test-project",
               "dataset": "test_dataset",
           }
       }
       response = await client.post(
           "/api/v2/data-connections/",
           json=payload,
           headers=auth_headers
       )
       assert response.status_code == 200
       data = response.json()
       assert data["engine"] == "bigquery"
   ```

### Performance Tests

1. **Connection Speed**

   - Measure time to establish connection
   - Target: < 5 seconds for first connection

2. **Query Performance**
   - Measure time to inspect large tables
   - Measure time to retrieve sample data

### Test Coverage Requirements

- Minimum 80% code coverage for new code
- All connection creation paths tested
- All error scenarios covered
- Integration tests with actual database (when credentials available)

---

## Deployment Considerations

### Environment Variables

Document required environment variables:

```bash
# For production
BIGQUERY_DEFAULT_PROJECT_ID=<project-id>
BIGQUERY_CREDENTIALS_PATH=/path/to/credentials.json

# For testing
BIGQUERY_PROJECT_ID=<test-project-id>
BIGQUERY_DATASET=<test-dataset>
BIGQUERY_CREDENTIALS='{"type": "service_account", ...}'
```

### Dependencies

Update deployment documentation:

1. **Docker Images**: Ensure Python dependencies are included in Docker builds
2. **Cloud Deployments**: Document any cloud-specific requirements (e.g., IAM roles for BigQuery)
3. **Network Requirements**: Document any firewall rules or network access needed

### Security Considerations

1. **Credential Storage**

   - All credentials are encrypted in the database (`enc_configuration` field)
   - Never log credentials or expose them in error messages
   - Use environment variables for test credentials only

2. **Least Privilege**

   - Document minimum required permissions for the database user/service account
   - Recommend read-only access unless write operations are needed

3. **Connection Timeouts**
   - Configure appropriate connection and query timeouts
   - Handle timeout errors gracefully

### Monitoring

1. **Logging**

   - Log connection creation attempts
   - Log connection failures with sanitized error messages
   - Track connection duration metrics

2. **Metrics**
   - Connection success/failure rates
   - Query execution times
   - Number of active connections

---

## Example: Adding BigQuery Support

Here's a complete example checklist for adding BigQuery:

### Phase 1: Core Implementation (Day 1-2)

- [ ] ✅ Add `BigqueryDataConnectionConfiguration` to `core/src/agent_platform/core/payloads/data_connection.py`
- [ ] ✅ Add "bigquery" to `DataConnectionEngine` literal
- [ ] ✅ Add `BigqueryDataConnectionConfiguration` to union type
- [ ] ✅ Add `BigqueryDataConnection` class
- [ ] ✅ Add `_parse_bigquery_config` method to `DataConnection` class
- [ ] ✅ Register parser in `_get_engine_parser`

### Phase 2: Dependencies (Day 2)

- [ ] ✅ Add `google-cloud-bigquery` to `core/pyproject.toml`
- [ ] ✅ Add `bigquery` to ibis-framework extras
- [ ] ✅ Run `make sync` to update dependencies

### Phase 3: Server Implementation (Day 2-3)

- [ ] ✅ Add `_create_bigquery_connection` method to `DataConnectionInspector`
- [ ] ✅ Update `create_ibis_connection` to handle "bigquery" engine
- [ ] ✅ Add BigQuery-specific error patterns to `_ERROR_PATTERNS`
- [ ] ✅ Create `server/src/agent_platform/server/utils/bigquery_utils.py` (if needed)

### Phase 4: Test Infrastructure (Day 3-4)

- [ ] ✅ Update `engine` fixture in `conftest.py` to include "bigquery"
- [ ] ✅ Add BigQuery configuration to `sdm_seed_data_connection_configuration`
- [ ] ✅ Create `_initialize_bigquery_database` function
- [ ] ✅ Update `initialize_data_base` fixture dispatcher
- [ ] ✅ Create `server/tests/spar/resources/semantic_data_models/bigquery/schema.sql`
- [ ] ✅ Create `server/tests/spar/resources/semantic_data_models/bigquery/data.sql`
- [ ] ✅ Create `server/tests/spar/resources/semantic_data_models/bigquery/README.md`

### Phase 5: Unit Tests (Day 4-5)

- [ ] ✅ Add connection creation tests
- [ ] ✅ Add configuration parsing tests
- [ ] ✅ Add error handling tests
- [ ] ✅ Run tests locally: `make test-unit`

### Phase 6: Integration Tests (Day 5-6)

- [ ] ✅ Set up BigQuery test environment
- [ ] ✅ Configure environment variables
- [ ] ✅ Run integration tests with actual BigQuery
- [ ] ✅ Verify semantic data model tests pass
- [ ] ✅ Test inspection endpoint

### Phase 7: UI Updates (Day 6-7)

- [ ] ✅ Coordinate with frontend team to update `@sema4ai/data-interface`
- [ ] ✅ Add BigQuery icon to icon library
- [ ] ✅ Test UI forms with new engine
- [ ] ✅ Verify data connection creation flow
- [ ] ✅ Test semantic data model creation with BigQuery

### Phase 8: Documentation (Day 7-8)

- [ ] ✅ Create BigQuery connection guide
- [ ] ✅ Update `docs/data-connections-integrations-erd.md`
- [ ] ✅ Update this document with lessons learned
- [ ] ✅ Create internal team documentation

### Phase 9: Review & Testing (Day 8-9)

- [ ] ✅ Code review with team
- [ ] ✅ End-to-end testing
- [ ] ✅ Performance testing
- [ ] ✅ Security review
- [ ] ✅ Documentation review

### Phase 10: Deployment (Day 9-10)

- [ ] ✅ Merge to main branch
- [ ] ✅ Deploy to staging environment
- [ ] ✅ Verify in staging
- [ ] ✅ Deploy to production
- [ ] ✅ Monitor for errors
- [ ] ✅ Update user-facing documentation

---

## Common Issues and Solutions

### Issue 1: Ibis Backend Not Found

**Symptom**: `ValueError: Unsupported engine for inspection: bigquery`

**Solution**:

1. Ensure backend is added to ibis-framework extras in `pyproject.toml`
2. Run `make sync` to update dependencies
3. Verify installation: `uv run python -c "import ibis; print(ibis.bigquery)"`

### Issue 2: Connection Timeout

**Symptom**: Connection takes too long or times out

**Solution**:

1. Add connection timeout parameter
2. Implement retry logic with exponential backoff
3. Add connection pooling if supported

### Issue 3: Authentication Errors

**Symptom**: "Authentication failed" or "Access denied"

**Solution**:

1. Add detailed error messages to `_ERROR_PATTERNS`
2. Document required permissions clearly
3. Provide troubleshooting steps in connection guide

### Issue 4: Type Compatibility Issues

**Symptom**: Errors when inspecting certain column types

**Solution**:

1. Add type mapping for database-specific types
2. Handle unsupported types gracefully (e.g., mark as "unknown")
3. Consider creating database-specific utility functions (like `snowflake_utils.py`)

### Issue 5: Tests Failing in CI/CD

**Symptom**: Tests pass locally but fail in CI

**Solution**:

1. Check environment variable configuration
2. Verify test credentials are properly secured
3. Consider using mocks for unavailable test databases
4. Document how to skip tests if credentials not available

---

## Database-Specific Considerations

### PostgreSQL-like Databases (MySQL, MariaDB, TimescaleDB, etc.)

- Often have similar connection parameters
- SSL configuration handling via `_parse_ssl_config`
- Schema and database concepts are similar
- Connection pooling is important

### Cloud Data Warehouses (BigQuery, Redshift, Snowflake, etc.)

- Authentication often involves IAM roles or service accounts
- May require special session parameters
- Query costs considerations
- May have specific data type limitations
- Often have schema/database hierarchy differences

### NoSQL Databases (if adding support)

- May not have traditional table/column structure
- Inspection logic may need significant customization
- Consider if semantic data models are appropriate

---

## Checklist Summary

Use this high-level checklist when adding any new database engine:

- [ ] Core configuration schema defined
- [ ] Configuration parser implemented
- [ ] Dependencies added to pyproject.toml
- [ ] Ibis connection method created
- [ ] Error handling implemented
- [ ] Test fixtures created
- [ ] Test SQL files created
- [ ] Unit tests written and passing
- [ ] Integration tests written and passing
- [ ] UI schema added to data-interface
- [ ] Database icon added
- [ ] Connection guide documentation written
- [ ] Code reviewed
- [ ] End-to-end testing completed
- [ ] Deployed to staging
- [ ] Deployed to production
- [ ] User documentation published

---

## Additional Resources

- [Ibis Backends Documentation](https://ibis-project.org/backends/)
- [Semantic Data Models Documentation](./data-frames-db-and-semantic-models.md)
- [Data Connections ERD](./data-connections-integrations-erd.md)
- [Development Guide](./development-guide.md)

---

## Getting Help

If you encounter issues or have questions:

1. Check existing implementations (Postgres, Snowflake) for reference
2. Review Ibis documentation for your specific backend
3. Consult with the platform team
4. Create detailed issue with error logs and reproduction steps

---

**Document Version**: 1.0  
**Last Updated**: 2025-01-07  
**Maintainer**: Platform Engineering Team
