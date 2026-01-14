# Verified Query Creation Flow

## Overview

Verified queries are created from data frames that were generated from SQL queries. The process involves extracting the SQL from a data frame, optionally verifying it, and then saving it to a semantic data model.

## API Endpoints

### 1. **Get Data Frame as Validated Query**

**Endpoint:** `POST /api/v2/threads/{tid}/data-frames/as-validated-query`

**Purpose:** Extracts a `VerifiedQuery` object from an existing data frame.

**Request:**

```json
{
  "data_frame_name": "my_data_frame"
}
```

**Response:** Returns a `VerifiedQuery` object with:

- `name`: Auto-generated from data frame name (via `data_frame_name_to_verified_query_name`)
- `nlq`: The data frame's description
- `sql`: The full SQL query that created the data frame (`full_sql_query_logical_str`)
- `verified_at`: Current timestamp
- `verified_by`: User ID
- `parameters`: Optional (for parameterized queries)

**Location:** `server/src/agent_platform/server/api/private_v2/threads_data_frames.py:1372`

**Key Logic:**

- Validates that the data frame was created from a SQL computation (`input_id_type == "sql_computation"`)
- Resolves the data frame to get the full SQL query string
- Converts the data frame name to a verified query name format

---

### 2. **Verify Verified Query**

**Endpoint:** `POST /api/v2/semantic-data-models/verify-verified-query`

**Purpose:** Validates a verified query before saving it. This is the step where parameter validation happens.

**Request:**

```json
{
  "semantic_data_model": { ... },
  "verified_query": {
    "name": "my_verified_query",
    "nlq": "Get customers in Germany",
    "sql": "SELECT * FROM customers WHERE country = :country",
    "parameters": [
      {
        "name": "country",
        "data_type": "string",
        "example_value": "Germany",
        "description": "Country to filter by"
      }
    ]
  },
  "accept_initial_name": "my_verified_query"
}
```

**Response:** Returns the verified query with validation errors (if any):

- `sql_errors`: SQL syntax errors, missing tables, table reference errors
- `parameter_errors`: Parameter validation errors (data type, example value, missing definitions)
- `nlq_errors`: NLQ validation errors
- `name_errors`: Name validation errors (uniqueness, format)
- `verified_at`: Timestamp
- `verified_by`: User ID
- `parameters`: Stored if validation passes

**Location:** `server/src/agent_platform/server/api/private_v2/semantic_data_model_api.py:1357`

**Key Validations:**

Validations are performed using Pydantic model validators integrated into `VerifiedQuery` and `QueryParameter` models:

1. **SQL Syntax and Table References**: Uses `sqlglot` to parse and validate SQL, then checks that all referenced tables exist in the semantic data model
2. **Parameter Validation** (performed by `QueryParameter` model validators):
   - Extracts parameters from SQL (`:param_name`)
   - Validates parameter definitions match SQL
   - Checks required fields (`name`, `data_type`, `description`)
   - `example_value` is **optional** (can be `None`)
   - Validates `data_type` is one of: `integer`, `float`, `boolean`, `string`, `datetime`
   - If `example_value` is provided, validates it matches `data_type`:
     - `integer`: Must be an `int`
     - `float`: Must be a number (`int` or `float`)
     - `boolean`: Must be a `bool`
     - `string`: Must be a `str`
     - `datetime`: Must be an ISO-8601 formatted string (e.g., `"2025-12-18T11:00:00Z"`)
   - Substitutes example values for SQL validation (if provided)
3. **Name Validation**: Checks format (letters, numbers, spaces only) and uniqueness within the semantic data model
4. **NLQ Validation**: Ensures NLQ is not empty

**Validation Approach:**

- Uses **fail-fast validation**: stops on first error in each validation method
- Custom exception classes (`VerifiedQuerySQLError`, `VerifiedQueryParameterError`, `VerifiedQueryNameError`, `VerifiedQueryNLQError`) for clear error categorization
- Errors are automatically grouped by the API layer into respective error lists

---

### 3. **Save Data Frame as Validated Query**

**Endpoint:** `POST /api/v2/threads/{tid}/data-frames/save-as-validated-query`

**Purpose:** Saves a verified query to a semantic data model.

**Request:**

```json
{
  "verified_query": {
    "name": "my_verified_query",
    "nlq": "Get customers in Germany",
    "sql": "SELECT * FROM customers WHERE country = :country",
    "verified_at": "2024-01-01T00:00:00Z",
    "verified_by": "user_id",
    "parameters": [ ... ]
  },
  "semantic_data_model_id": "sdm_id"
}
```

**Response:**

```json
{
  "message": "Successfully saved validated query 'my_verified_query'."
}
```

**Location:** `server/src/agent_platform/server/api/private_v2/threads_data_frames.py:1461`

**Key Logic:**

- Retrieves the semantic data model
- Validates the semantic data model structure
- Adds or updates the verified query in the `verified_queries` list
- Updates the semantic data model in storage

---

## Typical Workflow

### Frontend Flow (from `CreateVerifiedQueryFromDataFrameDialog.tsx`):

1. **User selects a data frame** to convert to a verified query
2. **User fills in form**:
   - Selects semantic data model
   - Optionally edits name, NLQ, SQL
   - For parameterized queries: adds parameter definitions
3. **Verify step** (optional but recommended):
   ```typescript
   const verifyResponse = await verifyMutation.mutateAsync({
     semantic_data_model: selectedModel,
     verified_query: queryToVerify,
     accept_initial_name: '',
   });
   ```
   - Checks for validation errors
   - If errors exist, shows them to user
4. **Save step**:
   ```typescript
   await saveMutation.mutateAsync({
     threadId,
     verifiedQuery: newQuery,
     semanticDataModelId: selectedModelId,
     agentId,
   });
   ```

### Backend Flow:

1. **Get Data Frame as Validated Query** (`/as-validated-query`):

   - Extracts SQL from data frame
   - Creates initial `VerifiedQuery` object
   - Returns to frontend

2. **Verify Verified Query** (`/verify-verified-query`):

   - Validates SQL syntax
   - Validates parameters (if present)
   - Checks table references
   - Returns validated query with errors

3. **Save Validated Query** (`/save-as-validated-query`):
   - Adds verified query to semantic data model
   - Updates storage

---

## Parameterized Queries Flow

For parameterized queries, the flow is:

1. **User creates data frame** with SQL like:

   ```sql
   SELECT * FROM customers WHERE country = 'Germany'
   ```

2. **User converts to verified query** and adds parameters:

   ```json
   {
     "sql": "SELECT * FROM customers WHERE country = :country",
     "parameters": [
       {
         "name": "country",
         "data_type": "string",
         "example_value": "Germany",
         "description": "Country to filter by"
       }
     ]
   }
   ```

3. **Verification**:

   - Extracts `:country` from SQL
   - Validates parameter definition matches
   - If `example_value` is provided ("Germany"), substitutes it into SQL for validation
   - Validates SQL syntax with substituted value (or original SQL if no example provided)
   - Parameter validation errors are returned in `parameter_errors` (separate from `sql_errors`)

4. **Saving**:

   - Stores verified query with parameters
   - Parameters are preserved on the verified query for future execution support

5. **Execution**:
   - Currently, `create_data_frame_from_verified_query` supports **only non-parameterized** verified queries.
   - Parameterized verified queries are **not executed** via this tool and are filtered out of the agent's
     SDM summary context so the agent never selects them.
   - In future we'll add a dedicated tool for executing parameterized verified queries.

---

## Forward Compatibility

The current implementation is **forward compatible** for future auto-detection of parameters:

- The `parameters` field in `VerifiedQuery` is optional
- All endpoints already handle optional parameters
- Future auto-detection can be added to `/as-validated-query` without API changes
- Existing clients will continue to work (they'll ignore auto-detected parameters)
- New clients can use auto-detected parameters

---

## Key Files

- **API Endpoints:**

  - `server/src/agent_platform/server/api/private_v2/threads_data_frames.py`
    - `get_data_frame_as_validated_query` (line 1372)
    - `save_data_frame_as_validated_query` (line 1461)
  - `server/src/agent_platform/server/api/private_v2/semantic_data_model_api.py`
    - `verify_verified_query` (line 1117)

- **Frontend:**

  - `workroom/spar-ui/src/components/DataFrame/CreateVerifiedQueryFromDataFrameDialog.tsx`
  - `workroom/spar-ui/src/queries/dataFrames.ts`

- **Types:**

  - `core/src/agent_platform/core/data_frames/semantic_data_model_types.py`
    - `VerifiedQuery` Pydantic model
    - `QueryParameter` Pydantic model
    - Custom exception classes: `VerifiedQuerySQLError`, `VerifiedQueryParameterError`, `VerifiedQueryNameError`, `VerifiedQueryNLQError`
    - Validation context: `VerifiedQueryValidationContext`
    - Validation logic integrated via Pydantic field validators and model validators

- **Utilities:**
  - `server/src/agent_platform/server/data_frames/sql_parameter_utils.py`
    - Parameter extraction, validation, substitution
  - `server/src/agent_platform/server/api/private_v2/semantic_data_model_api.py`
    - `prepare_verified_query_validation_context()`: Prepares validation context with available tables, existing query names, etc.
    - `_convert_pydantic_errors_to_validation_messages()`: Converts Pydantic validation errors to custom `ValidationMessage` format
