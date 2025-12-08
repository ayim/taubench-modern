Data Context Overview

### Data Frames
You have 1 data frames to work with. Details:

### Data Frame: test_data_frame
Description: A test data frame for testing purposes
Number of rows: 100
Number of columns: 5
Column names:
- col1
- col2
- col3
- col4
- col5

#### Raw Data Frames
```yaml
  - data_frame_id: <uuid>
    user_id: <uuid>
    agent_id: <uuid>
    thread_id: <uuid>
    num_rows: 100
    num_columns: 5
    column_headers:
      - col1
      - col2
      - col3
      - col4
      - col5
    name: test_data_frame
    input_id_type: file
    created_at: '<timestamp>'
    sheet_name: Sheet1
    computation_input_sources:
      source_1:
        source_type: data_frame
        source_id: some-data-frame-id
      source_2:
        source_type: data_frame
        source_id: external-postgres-connection-2
    file_id: <uuid>
    file_ref:
    description: A test data frame for testing purposes
    computation:
    parquet_contents: <20 bytes>
    extra_data:
      key: value

```

### Semantic Data Models
#### Semantic Model: test_model
- Description: Test semantic data model: test_model
- Updated at: <timestamp>

##### Table `test_entity`
Base table: {'database': 'test_db', 'schema': 'test_schema', 'table': 'test_table'}
Description: A test entity
- No dimensions, time dimensions, or facts defined.

#### Raw Semantic Data Models
```yaml
  - semantic_data_model_id: <uuid>
    semantic_data_model:
      name: test_model
      description: 'Test semantic data model: test_model'
      tables:
        - name: test_entity
          description: A test entity
          base_table:
            database: test_db
            schema: test_schema
            table: test_table
    agent_ids:
      - <uuid>
    thread_ids: []
    updated_at: '<timestamp>'
    references:
      data_connection_ids: []
      file_references: []
      data_connection_id_to_logical_table_names: {}
      file_reference_to_logical_table_names: []
      logical_table_name_to_connection_info:
        test_entity:
          kind: data_frame
          data_frame_name: test_table
      errors: []
      tables_with_unresolved_file_references: []
      semantic_data_model_with_errors:

```

### Data Frames System Prompt
```
## Data Frames Summary
-- available to be used in the following tools: data_frames_slice, data_frames_delete, data_frames_create_from_sql (may be referenced by the name as tables in the SQL query)

You have 1 data frames to work with. Details:

### Data Frame: test_data_frame
Description: A test data frame for testing purposes
Number of rows: 100
Number of columns: 5
Column names:
- col1
- col2
- col3
- col4
- col5



Note: It's possible to use an url such as 'data-frame://<data_frame_name>' to get the data frame in json format to use in vega-lite charts.

## Semantic Data Models (tables available to be used in the `data_frames_create_from_sql` tool):

**SQL SYNTAX RULES:**
- Reference tables by their logical name only (e.g., `FROM my_table`). Do NOT prefix with the model name.
- Always qualify column names with their table (e.g., `my_table.column_name`), especially in CTEs and JOINs.

### Model: test_model
SQL dialect: duckdb
Description: Test semantic data model: test_model
Table: test_entity
 Description: A test entity
```
