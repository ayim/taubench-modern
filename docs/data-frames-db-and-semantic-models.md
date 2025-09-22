# References for semantic data models:

- [Snowflake semantic model generator](https://github.com/Snowflake-Labs/semantic-model-generator)
- [Snowflake semantic model spec](https://docs.snowflake.com/en/user-guide/snowflake-cortex/cortex-analyst/semantic-model-spec)

# Step 1:

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

# Step 2:

`Feature`: add the concept of a semantic data model in the agent server database.

Related information (in agent server database):

- Existing table: `v2_data_connection`: has the information to connect to a database (name, description, engine, connection parameters)
- Existing table: `v2_file_owner`: has the information of a file (file_ref, thread_id)

- New table: `v2_semantic_data_model` holds information for a data model (based on the snowflake semantic data model) and junction tables for references.

  - The model can reference:
    - multiple databases (by referencing the `v2_data_connection.id`, which is "global" in the agent server db)
    - multiple files (by referencing the `v2_file_owner.thread_id` and `v2_file_owner.file_ref`)
  - The semantic data model itself will be stored in a json column.

    - Note: the semantic model types in python can be found in [`core/src/agent_platform/core/data_frames/semantic_model.py`](../core/src/agent_platform/core/data_frames/semantic_model.py).

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
  - `set_semantic_data_model`, which receives a `SetSemanticDataModelPayload` needs to accept a `dict` with the semantic data model and a list of `data_connection_id`s and `file_reference`s (thread_id and file_ref) (REST API: `PUT /api/v2/semantic-data-models/{semantic_data_model_id}/input-data-connections`) -- if the `uuid` is not provided, a new one will be created.
  - `get_semantic_data_model`, which receives a `GetSemanticDataModelPayload` needs to accept a `semantic_data_model_id` and return a `dict` with the semantic data model (REST API: `GET /api/v2/semantic-data-models/{semantic_data_model_id}`).
  - `delete_semantic_data_model`, which receives a `DeleteSemanticDataModelPayload` needs to accept a `semantic_data_model_id` and delete the semantic data model (REST API: `DELETE /api/v2/semantic-data-models/{semantic_data_model_id}`).

Note: in this APIs, the semantic data model is passed as json, the data_connection_ids and file_references are extracted from
the semantic data model tables specified (so, it's implicit in the semantic data model what connections and files are used,
those are extracted from the schema to build those junction tables).

For files the model has to specify in the base_table the thread_id (as the database) and file_ref (as the schema) and
potentially the sheet name (as the table).

For data connections the model has to specify in the base_table the data_connection_id (and then specify the database,
schema and table as usual -- note that the database and schema are not required for all databases
(as not all databases have a database and schema -- i.e.: SQLite).

# Step 3:

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

# Step 4:

`Feature`: Create a semantic data model (initially pretty simple, maybe just
tables/columns/sample data) and pass it to the agent when needed in a way that allows the agent to recognize
that the data source and the related tables may be queried by the agent.

`Decision`: the Semantic Data Model can reference multiple databases or files at once.

`Note`: when a semantic data model is later needed just for a subset (say a semantic data model was created from 2 databases and a file), if
later on a file is required, it should be possible to extract a subset of the semantic data model to be used just for that file.
i.e.: semantic models are "globally" available and it should be possible to reuse a semantic model (or a part of it) when needed
when creating a new semantic data model for some other data (if the shape of one model is a subset or superset of another model).

`Requirement`: Create semantic data model using the agent server:

`Requires`:

- Data connections of interest

- Files of interest (based on the related created data frames)

Agent Server related APIs:

- Existing REST API which allows collecting sheets/columns/sample data from a file (dataframe API)

- New API to auto-generate a semantic model based on the tables/columns/samples for a file/data source as well as details given by the user.

  - `Note`: the UI must collect the information and then call this new API to actually build the semantic data model.
  - `Note`: the initial implementation will be very simple, not agentic.

- Storing the semantic data model should be done using the APIs from step 2.

# Step 5:

`Feature`: Enable the user to create data frames from a data source.

Right now we have a tool to create a "data frame from a file" which receives a file reference in the thread + sheet name if needed
and another tool to create a data frame from a sql which may reference existing data frames. For this feature, we don't need
to create a new tool, but we need to extend the sql so that it can target existing data connections and it must be always
available, not only when a data frame is already created and we need to build the prompt for the agent accordingly.

Also, we need to be able to run the queries in a way that allows queries to be run containing both data frames created from
files as well as sql targetting a data source to extract table information from a database.

# Step 6:

Create a "Full semantic data model" which includes metrics, facts, dimensions, etc.

Extract primary keys/uniqueness from the database directly when available.
