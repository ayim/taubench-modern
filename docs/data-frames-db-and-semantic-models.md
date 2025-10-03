# References for semantic data models:

- [Snowflake semantic model generator](https://github.com/Snowflake-Labs/semantic-model-generator)
- [Snowflake semantic model spec](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst/semantic-model-spec)
- [UI Mockups](https://www.figma.com/design/nQPS1LcxbxaSp1TBqGFpOy/Spar-UI?node-id=2089-3400)

# Step 1 (done):

`Feature`: associate a list of data connections to an agent.

Related information (in agent server database):

- Existing table: `v2_data_connection`: has the information to connect to a database (name, description, engine, connection parameters)

- New `v2_agent_data_connections` junction table to reference data connections and agents:

```sql
v2_agent_data_connections -- junction table (references agent id and data source id)
    agent_id TEXT NOT NULL,
    data_source_id TEXT NOT NULL,
```

- Create new APIs to add/remove a data connection to an agent.
  - `set_agent_data_connections`, which receives a `SetAgentDataConnectionsPayload` needs to accept a `agent_id` and a list of `data_connection_id`s (REST API: `PUT /api/v2/agents/{agent_id}/data-connections`).
  - `get_agent_data_connections`, which receives a `GetAgentDataConnectionsPayload` needs to accept an `agent_id` and return a list of `DataConnection`s (REST API: `GET /api/v2/agents/{agent_id}/data-connections`).

# Step 2 (done):

`Feature`: add the concept of a semantic data model in the agent server database.

Related information (in agent server database):

- Existing table: `v2_data_connection`: has the information to connect to a database (name, description, engine, connection parameters)
- Existing table: `v2_file_owner`: has the information of a file (file_ref, thread_id)

- New table: `v2_semantic_data_model` holds information for a data model (based on the snowflake semantic data model) and junction tables for references.

  - The model can reference:
    - multiple databases (by referencing the `v2_data_connection.id`, which is "global" in the agent server db)
    - multiple files (by referencing the `v2_file_owner.thread_id` and `v2_file_owner.file_ref`)
  - The semantic data model itself will be stored in a json column.

    - Note: the semantic model types in python can be found in [`core/src/agent_platform/core/data_frames/semantic_data_model_types.py`](../core/src/agent_platform/core/data_frames/semantic_data_model_types.py).

  - Format (pseudo-code, constraints not included) of the table:

    ```sql
    v2_semantic_data_model -- table
        id UUID PRIMARY KEY,
        semantic_model JSONB NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT (CURRENT_TIMESTAMP AT TIME ZONE 'UTC'),

    v2_semantic_data_model_input_data_connections -- junction table (references semantic data model id and data connection id)
        semantic_data_model_id UUID NOT NULL,
        data_connection_id UUID NOT NULL,

    v2_semantic_data_model_input_file_references -- junction table (references semantic data model id and file reference)
        semantic_data_model_id UUID NOT NULL,
        thread_id UUID NOT NULL,
        file_ref TEXT NOT NULL,
    ```

- Create new APIs to add/remove a data connection to an agent.
  - `set_semantic_data_model`, which receives a `SetSemanticDataModelPayload`
    - `PUT /api/v2/semantic-data-models/{semantic_data_model_id}`
    - `POST /api/v2/semantic-data-models`
    - Note: the connections and file references are extracted from the semantic data model to populate the junction tables.
      i.e.: A `base_table` in the semantic data model must have either a `data_connection_id` (str)
      or a `file_reference` (dict with `thread_id` and `file_ref` and optionally `sheet_name`).
  - `get_semantic_data_model`, which receives a `GetSemanticDataModelPayload`
    - `GET /api/v2/semantic-data-models/{semantic_data_model_id}`
  - `delete_semantic_data_model`, which receives a `DeleteSemanticDataModelPayload`
    - `DELETE /api/v2/semantic-data-models/{semantic_data_model_id}`

Note: in this APIs, the semantic data model is passed as json, the data_connection_ids and file_references are extracted from
the semantic data model tables specified (so, it's implicit in the semantic data model what connections and files are used,
those are extracted from the schema to build those junction tables).

For files the model has to specify in the base_table the thread_id (as the database) and file_ref (as the schema) and
potentially the sheet name (as the table).

For data connections the model has to specify in the base_table the data_connection_id (and then specify the database,
schema and table as usual -- note that the database and schema are not required for all databases
(as not all databases have a database and schema -- i.e.: SQLite).

# Step 3 (done):

`Feature`: Inspect data connections for tables/columns/sample data.

- New REST API to collect tables/columns/sample data for a data source.

API:

- `POST /api/v2/data-connections/{data_connection_id}/inspect` (it's a POST because it should receive a body with the information to inspect)

The API must:

1. Be implemented in `server/src/agent_platform/server/api/private_v2/data_connections.py`
2. Get the data connection information. Input:

```python
@dataclass
class TableToInspect:
    name: str
    database: str | None
    schema: str | None
    # If the columns are passed, inspect only those columns, if not passed, inspect all columns
    columns_to_inspect: list[str] | None = None

@dataclass
class DataConnectionsInspectRequest:
    # If the tables are passed, inspect only those tables, if not passed, inspect all tables
    tables_to_inspect: list[TableToInspect] | None = None
```

3. Based on the data connection type, get the tables/columns/sample data
   - Right now we need to support only the following:
     - SQLite
     - Postgres
     - Redshift
     - Snowflake
   - Note: we should get the information using ibis to collect the database metadata.
   - The API should be implemented in `server/src/agent_platform/server/api/private_v2/data_connections.py`
4. Return the information in the following format:

```python
@dataclass
class ColumnInfo:
    name: str
    data_type: str
    sample_values: list[Any] | None
    primary_key: bool | None
    unique: bool | None
    description: str | None
    synonyms: list[str] | None

@dataclass
class TableInfo:
    name: str
    database: str | None
    schema: str | None
    description: str | None
    columns: list[ColumnInfo]

@dataclass
class DataConnectionsInspectResponse:
    tables: list[TableInfo]
```

# Step 4 (done):

`Feature`: Generate a semantic data model (initially pretty simple, just tables/columns/sample data but in the snowflake semantic data model format, see types in: [`core/src/agent_platform/core/data_frames/semantic_data_model_types.py`](../core/src/agent_platform/core/data_frames/semantic_data_model_types.py)) and pass it to the agent when needed in a way that allows the agent to recognize
that the data source and the related tables may be queried by the agent.

`Note`: the Semantic Data Model can reference multiple databases or files at once.

`Requirement`: Create semantic data model using the agent server:

`REST-API`:

- `POST /api/v2/semantic-data-models/generate`

Receives a `GenerateSemanticDataModelPayload` with the following fields:

```python
class ColumnInfo:
  name: str
  data_type: str
  sample_values: list[Any] | None
  description: str | None
  synonyms: list[str] | None

class TableInfo:
  name: str
  database: str | None
  schema: str | None
  description: str | None
  columns: list[ColumnInfo]

class DataConnectionInfo:
  data_connection_id: str
  tables_info: list[TableInfo]

class FileInfo:
  thread_id: str
  file_ref: str
  sheet_name: str | None
  tables_info: list[TableInfo]

class GenerateSemanticDataModelPayload:
  name: str
  description: str | None
  data_connections_info: list[DataConnectionInfo]
  files_info: list[FileInfo]

```

It then returns the semantic data model in the snowflake semantic data model format.

The idea is that the client (UI) should:

- Use the existing REST API(s) which allows collecting sheets/columns/sample data from a data source or a file.

- Call the new API to generate the semantic data model.

- Store the semantic data model using the APIs from step 2.

# Step 5 (done):

`Feature`: associate a list of semantic data models to an agent or a thread (conversation).

Related information (in agent server database):

- Existing table: `v2_semantic_data_model`: has the information related to the semantic data model

- New `v2_agent_semantic_data_models` junction table to reference semantic data models and agents:
- New `v2_thread_semantic_data_models` junction table to reference semantic data models and threads:

```sql
v2_agent_semantic_data_models -- junction table (references agent id and semantic data model id)
    agent_id TEXT NOT NULL,
    semantic_data_model_id TEXT NOT NULL,

v2_thread_semantic_data_models -- junction table (references thread id and semantic data model id)
    thread_id TEXT NOT NULL,
    semantic_data_model_id TEXT NOT NULL,
```

- Create new APIs to add/remove a semantic data model to an agent or a thread.
  - `set_agent_semantic_data_models`, which receives a `SetAgentSemanticDataModelsPayload` needs to accept a `agent_id` and a list of `semantic_data_model_id`s (REST API: `PUT /api/v2/agents/{agent_id}/semantic-data-models`).
  - `get_agent_semantic_data_models`, which needs to accept an `agent_id` and return a list of `SemanticDataModel`s (REST API: `GET /api/v2/agents/{agent_id}/semantic-data-models`).
  - `set_thread_semantic_data_models`, which receives a `SetThreadSemanticDataModelsPayload` needs to accept a `thread_id` and a list of `semantic_data_model_id`s (REST API: `PUT /api/v2/threads/{thread_id}/semantic-data-models`).
  - `get_thread_semantic_data_models`, which needs to accept a `thread_id` and return a list of `SemanticDataModel`s (REST API: `GET /api/v2/threads/{thread_id}/semantic-data-models`).

# Step 6 (done):

Create a new REST API to list all semantic data models (agent_id and thread_id can be used as filters).

- `GET /api/v2/semantic-data-models` which receives a `GetSemanticDataModelsPayload` with the following fields:
  - `agent_id`: str | None
  - `thread_id`: str | None

It should return a list of `SemanticDataModel`s along with information on which agent(s) or thread(s) each semantic data model is associated with, besides the semantic data model itself and the data connections and file references.

i.e.:

```python

class FileReference:
  thread_id: str
  file_ref: str
  sheet_name: str | None

class SemanticDataModelWithAssociations:
  semantic_data_model: SemanticDataModel
  agent_ids: list[str]
  thread_ids: list[str]
  data_connection_ids: list[str]
  file_references: list[FileReference]
```

# Step 7:

`Feature`: Enable the user to create data frames from a data source (note: at this moment "federated" queries
are not supported, so, only SQL referencing a single data connection is supported).

Right now we have a tool to create a "data frame from a file" which receives a file reference in the thread + sheet name if needed
and another tool to create a data frame from a sql which may reference existing data frames. For this feature, we don't need
to create a new tool, but we need to extend the sql so that it can target existing data connections and it must be always
available, not only when a data frame is already created and we need to build the prompt for the agent accordingly.

Also, we need to be able to run the queries in a way that allows queries to be run containing both data frames created from
files as well as sql targetting a data source to extract table information from a database.

i.e.: the DataFramesKernel should be able to target tables in data connections (based on the semantic data models that
are accessible both in the thread as well as in the agent).

Structure:

A `DataFrameSource` should be extended to support `semantic_data_model` as a source type.

- When a `semantic_data_model` is used, information on the `base_table` and `logical_table_name` must be provided.
- The `base_table` information can contain info either on a data connection or a file reference (which can be
  specified in the semantic data model).

When resolving the sources for the SQL computation, if the names required are not found in the data frames, it should be
possible to resolve them using the semantic data models. In this case, the `PlatformDataFrame` will contain
a `computation_input_sources` field which will contain the `DataFrameSource`s that are needed to resolve the data frame
(which in turn can be resolved using the semantic data model).

Note: there should be a "translation" step because the LLM will reference the "logical table name" but then
the SQL must later on reference the actual table (using the `base_table` information).

Note: up to now, a file would need to be directly converted to a data frame (so a `PlatformDataFrame` with
`input_id_type` set to `file`), but in the semantic data model use case, this is not the case, a `PlatformDataFrame`
will just define the `input_id_type` as `sql_computation` and the `computation_input_sources` will contain the
information on the semantic data model that must be queried.

In this step, all the `computation_input_sources` must reference the same connection id (if more than
one connection is used we'll fail).

In the code we must:

- Create a dependency graph to determine the endpoints (data connections, files, dependent sql computations) that need to be queried.
- After the dependency graph is created, actually "resolve" it to create the data frame.
