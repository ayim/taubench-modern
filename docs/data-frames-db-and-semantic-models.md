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
        semantic_data_model_id TEXT NOT NULL,
        data_connection_id TEXT NOT NULL,

    v2_semantic_data_model_input_file_references -- junction table (references semantic data model id and file reference)
        semantic_data_model_id TEXT NOT NULL,
        thread_id TEXT NOT NULL,
        file_ref TEXT NOT NULL,
    ```

# Step 3:

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

- Files of interest

Agent Server related APIs:

- Existing REST API which allows collecting sheets/columns/sample data from a file (dataframe API)

- New REST API(s) to collect tables/columns/sample data for a data source(s).

  - We may have to do it in a way that the UI can query parts of it to build a tree as needed (depends on how much data is available fast in a single call).

- New API to auto-generate a semantic model based on the tables/columns/samples for a file/data source as well as details given by the user.

  - `Note`: the UI must collect the information and then call this new API to actually build the semantic data model.
  - `Note`: the initial implementation will be very simple, not agentic.

- Storing the semantic data model:
  - The semantic data model by itself will be stored as json in the DB (in the v2_semantic_data_model) and it should reference
    the inputs that were used to build it.
  - Right now we collect the tables/columns/sample data from data frames to provide to the LLM, now, after a semantic data model is available,
    instead of that information, "multiple" semantic data models will be fetched from the database and passed in place
    of that information (as it should be a superset). Fetching should be done based on the data connections available as
    well as the files being currently used.

`Note`: at this point, further reviewing and editing a semantic data model is always done as a whole (so, there'll be CRUD apis
related to the semantic data model -- the UI can initially just show the json -- maybe as a yaml to be a bit more readable).

# Step 4:

`Feature`: Enable the user to create data frames from a data source.

Right now we have a tool to create a "data frame from a file" which receives a file reference in the thread + sheet name if needed
and another tool to create a data frame from a sql which may reference existing data frames. For this feature, we don't need
to create a new tool, but we need to extend the sql so that it can target existing data connections and it must be always
available, not only when a data frame is already created and we need to build the prompt for the agent accordingly.

Also, we need to be able to run the queries in a way that allows queries to be run containing both data frames created from
files as well as sql targetting a data source to extract table information from a database.

# Step 5:

Create a "Full semantic data model" which includes metrics, facts, dimensions, etc.
