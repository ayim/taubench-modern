# Data frames

Data frames in the agent server context mean some tabular data that is stored in the agent server.
It should usually be initially provided by the user through a file upload (say a csv file or
an excel file -- note that an excel file may end up having multiple sheets, which means
that we may actually have multiple data frames from one single file).

Also, a data frame could be created automatically if some action/tool returns tabular data
(i.e.: an action/mcp tool that returns an object with a Response[Table(columns, rows)] or just
Table(columns, rows) shape).

# Notes for development:

- `pytest` is used to run tests and tests should be done top-level (i.e.: not inside a class)
- `pytest` should be run with `uv run python -m pytest <args>` from the root of the project.
- The tests shouldn't be extensive, they should be focused on the new code and the new functionality.

## To run integrated with Studio

Start agent server and then start Studio in another terminal:

```bash
make run-as-studio

# On studio (using the `develop` branch`):
set SEMA4AI_STUDIO_SUDO_BLOCK_AGENT_SERVER_LAUNCH=yes
npm i
npm run force-clean-clis
npm run cpb
npm run vite-bs
```

## To run integrated with SPAR

Start agent server and then start SPAR in another terminal:

```bash
make run-server

cd workroom
npm i
npm run dev
```

# References:

[Miro board: Internals behind the Data Model API in Agent Server](https://miro.com/app/board/uXjVImChMn0=/?moveToWidget=3458764636556067436&cot=14)
[Linear: Data frames](https://linear.app/sema4ai/project/dataframes-fka-tables-4c740da3f7f2/overview)
[Figma: Data frames](https://www.figma.com/design/rNDLIqnUCT0SaiBWUvnpcL/Sema4.ai-Studio?node-id=12139-208045&t=r5IlfyVdDwYGrvFt-4)
[Hackaton for data frames](https://github.com/Sema4AI/agent-platform/compare/main...hackathon/better-tables)

# Workflow supported (phase 1)

- User uploads a csv or excel file.
- At that point the user is then asked if he wants to treat that file as a data frame.
  - Feature needed: Given a file upload, generate an "agent" message that asks what the user wants to do with the file.
    - One option should be: "Generate Data Frame"

# What happens when a user uploads a file you may ask:

1. The agent server API to upload a file is called in Studio (workroom) and then an attachment message is automatically created right
   afterwards (from the UI). Something as:

   ```typescript
   const uploadedFiles = await apiClient.uploadFiles(...)
   ...
   // Stream a new message with "attachment" kind
   // https://github.com/Sema4AI/agents-workroom/blob/main/src/components/Files.tsx#L110
   streamManager.initiateStream(createAttachmentMessage(...), currentChatId, agentId);
   ```

Internally the agent server deserializes that as a `ThreadAttachmentContent` message and that becomes something as `Uploaded [{attachment_content.name}]({attachment_content.uri})` when sent to the agent.

Note: it uses the `uri` when referenced here which is something as `agent-server-file://${file.file_id}`.

Note2: this is different from when the file is uploaded by an action/tool where none of the above happens (the file just
"appears" in the chat sidebar without any further processing -- also, the file in this case is nearly invisible in the thread,
it just appears in the related storage).

Given that, new APIs will be added to the agent server to create data frames from the internal file ids, but the `ThreadAttachmentContent`
will not be used (as we should be able to create data frames even from files that are uploaded by actions/tools).

REST APIs created:

- threads/{thread_id}/inspect-file-as-data-frame (GET)
- threads/{thread_id}/data-frames/from-file (POST)
- threads/{thread_id}/data-frames (GET)

# Current implementation step:

- Create (builtin) tools that can be used by the agent to create new data frames based on existing data frames based on some computation (SQL)

For this we need to:

## Step 1 (done):

Create a new REST API:

- threads/{thread_id}/data-frames/from-computation (POST)

- Create a new REST API to create a new data frame from an existing data frame based on some computation (SQL).
  - The REST API should be created in the `server/src/agent_platform/server/api/private_v2/threads.py` file.
  - The actual implementation should be created in a new file in the `server/src/agent_platform/server/data_frames/` directory.
- The input should reference the existing data frame(s) by their name
  - The tables in the thread should be listed and a dict with the name -> data frame should be created
- A simple SQL query should be provided by the user to compute the new data frame
- Using ibis we should create the pipeline to compute the new data frame
- Evaluate the result of the query to see if it works as expected
- If it does, create a new data frame with the result
- If it doesn't, return an error message to the user
- The new data frame should be added to the thread

## Step 2 (done):

Create a new REST API:

- threads/{thread_id}/data-frames/slice (POST)

- Create a new REST API which allows the client to obtain sliced data frame contents.
  - The data sent in the wire should follow either the parquet format or the json format (passed as an 'output_format' parameter).
  - The API requires a user.
  - The API requires a thread id.
  - The API requires either a data frame id or a data frame name.
  - The API requires an offset (optional) and a limit (optional) as well as column_names (optional).
    - If offset is not provided it starts with `0`
    - If limit is not provided it ends with the last row of the data frame
    - If column_names is not provided it returns all columns
  - The API returns a stream of data (either a parquet stream or a json stream).

Implementation-wise we must:

- Create the new REST API
- Change DataNodeResult (in `server/src/agent_platform/server/data_frames/data_node.py`) to include a `slice` method (which receives the offset, limit, column_names and format and returns the actual data, as a bytes -- either a json converted to bytes or a parquet created from pyarrow and then converted to bytes).

## Step 3 (done):

- Create the following builtin tools:
  - Create data frame from file (always available even if no data frames are available)
  - The ones below should only be available if there are data frames available:
    - Create data frame from computation
    - Delete data frame
    - Slice data frame
- Update the runbook system prompt so that such tools and the related dataframes are available to the agent.

Note: currently requires env var `SEMA4AI_AGENT_SERVER_ENABLE_DATA_FRAMES=1` to enable feature.

## Step 4 (done):

- Use `agent_settings.enable_data_frames` for feature flag to enable data frames for specific agents
  - Env var `SEMA4AI_AGENT_SERVER_ENABLE_DATA_FRAMES=1` can be kept as is, which would enable data frames for all agents
  - The setting in the `agent_settings` should be named `enable_data_frames` (boolean)
  - If either `SEMA4AI_AGENT_SERVER_ENABLE_DATA_FRAMES` is set or `agent_settings.enable_data_frames` is set to `true` then the data frames feature is enabled for the agent.

# Step 5 (done):

- Provide more info for the UI (in the `_DataFrameCreationAPI`):
  - If a data frame was created from file then file reference (input_id_type = "file")
  - If a data frame was created from different data frames then parent data frame ids (input_id_type = "sql_computation")
  - If a data frame was created from an in-memory data frame no additional info is needed (input_id_type = "in_memory")

# Step 6 (done)

- Show sample data in the LLM summary

# Step 7 (done)

- Don't remove tools after they were added into the context

# Step 8 (done)

- Make the result of named queries (Tables) be available as data frames automatically.

  Note: a named query is an LLM tool call that returns a json with a result with a shape such as:

  ```json
  {
    "result": {
      "columns": ["column1", "column2"],
      "rows": [
        [1, 2],
        [3, 4]
      ]
    }
  }
  ```

  or directly as a Table:

  ```json
  {
    "columns": ["column1", "column2"],
    "rows": [
      [1, 2],
      [3, 4]
    ]
  }
  ```

  The idea here is that when tool is returned and the result has that shape, we should create a new data frame from it automatically.

# Step 9 (done)

- Allow the LLM to use vega to show charts using data frames.

  - Currently the LLM is instructed to use vega-lite to show charts
    embedding the data or using some external url (no relative file paths or private URLs).

  Example for data:

  ```json
  {
    "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
    "data": {
      "values": [
        { "q": "Q1", "sales": 120 },
        { "q": "Q2", "sales": 95 }
      ]
    },
    "mark": "bar",
    "encoding": {
      "x": { "field": "q", "type": "ordinal", "title": "Quarter" },
      "y": { "field": "sales", "type": "quantitative", "title": "Units sold" }
    }
  }
  ```

  Example for url:

  Same as above but with the data specified as something as:

  ```json
  {
    "data": {
    "url": "data/seattle-weather.csv",
    "format": {
      "type": "csv"
    }
  },
  ```

  -- types may be: CsvDataFormat (comma separated values), DsvDataFormat (custom char separated values), JsonDataFormat (json), TopoDataFormat (topological info)

  Ok, now, given that, to show the chart should be "as simple as" making the values of the data frame available
  so that vega-lite can use them.

  So, the proposal is to make all the data from a data frame available as a url that can be used by vega-lite.

  Implementation-wise the suggestion is:

  - Add a new REST API to get the data from a data frame in the json format.
  - The REST API would be something as:
    - `GET /threads/{thread_id}/data-frames/{data_frame_name}&format=json`

  The LLM will be instructed to build the url with something as:

  - `data-frame://{data_frame_name}`
  - The UI component must do the appropriate conversion of the url based on the current thread being shown to build
    the full url.

Example:

curl -X GET http://localhost:58885/api/v2/threads/116745a4-4150-4eb5-9740-da9022c05238/data-frames/top_countries_highest_mortality_last_5_years -H "accept: application/json"

# Step 10 (done)

- Create semantic data model concept.
- Assign data sources to an agent.
- Inspect data sources for tables/columns/sample data.
- Build semantic data model (simple, maybe just tables/columns/sample data).
- Load data frames from a database.
- Enabling/Disabling data frames should be opt-out, not opt-in.

See [./data-frames-db-and-semantic-models.md](data-frames-db-and-semantic-models.md) for more details.

# Step 11 (done)

- https://sema4ai.slack.com/archives/C06CYLQ7S4R/p1758018826886949 (

  - Remove `data_frame_` prefix from the data frame name, current logic is `data_frame_<slugified(action_name)>`, we can make it simply `<slugified(action_name)>`).
  - We could also add name and description to the Table so that the user could have more control over it.)

- Add more logging related to what's happening when resolving the data frames/semantic data models.

# Step 11a (done)

- Fixed issue where creating a data frame from a csv with no values for one of the columns makes the data frame unusable afterwards.
  Note: this happens because duckdb doesn't support null column types (it does accept having null values in the column if the
  column is of a different type though, so, casting the column to string as a workaround).

# Step 11b (done)

- Provide an API which would receive the file contents of a file, then create a `create_file_data_reader_from_contents`
  to create a `FileDataReader` instance ad then create a `DataConnectionsInspectResponse` to return based on the
  data frames data.

Notes:

- The API should just receive the bytes of the file in the body.
- The file name should be passed as a header.
- It should be created next to the `inspect_data_connection` API (in `server/src/agent_platform/server/api/private_v2/data_connections.py`).
- Create an integration test in `test_data_frames_integration.py` to test the new API (update the agent client to support the new API).
- Do NOT run the tests, just create it.

# Step 12 (done):

Create a "Full semantic data model" which includes metrics, facts, dimensions, time dimensions, synonyms, etc.

Note: this is an "agentic" step, so, it should be done by using the `prompt_generate` API.

The idea is that we'll already have a "base" semantic data model (with tables, columns, sample data) and then we'll
enhance it with additional information.

We should:

1. Create a prompt for the LLM where we'll provide the current semantic data model.

- The prompt should:

  - Ask for better descriptions for the tables
  - Ask to improve the "logical" name of the table (the initial name should be considered as that's what's in the database, but it should be treated as a hint)
  - Ask to add synonyms to the tables
  - Ask for better names for the columns (the initial name should be considered as that's what's in the database, but it should be treated as a hint)
  - Ask for better descriptions for the columns
  - Ask to re-categorize the columns into dimensions, facts, metrics, time dimensions (the initial categorization should be treated as a hint)

  To get the output, we should have a simple way of passing the data and then the LLM should output the data in json format.

  The information we're interested in having in the output is something as:

  ```json
  {
    "tables": [
      {
        "new_name": "table1",
        "original_name": "table1",
        "description": "Better description for table1",
        "synonyms": ["table1_synonym1", "table1_synonym2"],
        "columns": [
          {
            "new_name": "column1",
            "original_name": "column1",
            "description": "Better description for column1",
            "synonyms": ["column1_synonym1", "column1_synonym2"],
            "category": "dimension"
          }
        ]
      }
    ]
  }
  ```

- The algorithm should be able to do a few rounds of iterations to improve the semantic data model, doing something as:
  - Ask the LLM for improvements
  - Verify using the LLM if the improvements are good
  - Ask again if the improvements were not good enough
  - Apply the improvements (either after a few rounds or after the LLM confirms that the improvements are good enough)

2. Run that prompt through the `prompt_generate` API.
3. Collect the response from the LLM and update the semantic data model accordingly.

This must be implemented in `server/src/agent_platform/server/kernel/semantic_data_model_generator.py` (in the `enhance_semantic_data_model` method).

The `suggest_scenario_from_thread` method from `server/src/agent_platform/server/evals/advisor.py` can be used as a reference on how to use
the `prompt_generate` API.

# Step 13 (done):

- We have the following issue: when a semantic data model that references a file is
  added to an agent, we can't really reference the actual file because it will only
  be valid after the user uploads it in a thread.

# Step 13a (done):

- Create a new integration test (in `server/tests/integration/test_semantic_data_models_integration.py`) that:
  1. Creates a csv file in memory
  2. Uses the API to inspect the file in-memory to extract contents as if it was a database
  3. Creates a semantic data model from it
  4. Create a new thread
  5. Upload that file to the thread
  6. Actually ask the LLM which semantic data models it has available

# Step 13b (done):

Actually make it possible to use that semantic data model with a file in a thread.

Note: this is tricky because we don't have a good way to make the link that a given file in the
thread is the same file that was used to create the semantic data model.

The process we go through is that at each processing step we check if semantic data models
have unresolved file references and if they have we try to resolve them.

At this point we'll do it without any caching to try to keep the PR as small as possible
(which is already quite big).

# Step 13c:

- Add caches for the inspection metadata when a file is inspected for tabular data (data frames).
- Add cache associating which file matches which semantic data model when a semantic data model is
  added to an agent (but the file is only available after it's uploaded to the thread).

# Step 14:

https://sema4ai.slack.com/archives/C07LMU0AQFR/p1759853149588429

- When the user uploads a file, the UI will stream an `attachment` message. The backend when converting that
  message to the prompt (in `_user_thread_contents_to_prompt_contents`) will see what's available
  in the context (data frames, doc intel, excel actions, etc.) and then will ask the agent to do
  something based on that.

  Example of one of the heuristics:

  - If there are only data-frame actions available and it's an excel file at that point
    it should inspect the file for multiple sheets and then request the agent to ask the
    user to select which sheet to create a data frame from.

# Step 15:

Actually do tests with postgres, redshift and snowflake.
Do more tests on exceptional use cases (slow queries, bad network, etc.).

# Step 16:

Support "federated" queries (i.e.: SQL referencing multiple data connections or referencing a data connection and a file or in-memory data).

# Step 17:

When a semantic data model is later needed just for a subset (say a semantic data model was created from 2 databases and a file), if
later on a file is required, it should be possible to extract a subset of the semantic data model to be used just for that file.
i.e.: semantic models are "globally" available and it should be possible to reuse a semantic model (or a part of it) when needed
when creating a new semantic data model for some other data (if the shape of one model is a subset or superset of another model).

# Future work (not right now):

- sema4ai.actions improvements:
  - Consume data frames directly from actions/tools.
  - Validate if user tries to create a Table with inconsistent column/rows.
  - Accept name and description for a Table.
- Bug in agent server: only a `Response[Table]` is accepted, but just a `Table` should be accepted too.
- Verify that errors with proper messages are returned to the LLM.
- Extract primary keys/uniqueness from the database directly when available.
- https://sema4ai.slack.com/archives/C07LMU0AQFR/p1758257549592739
  - make is so that the agent understands an existing data frame cannot be overwritten.
- Versioning of data frames (or provide more information to the UI so that it can know what's supposed to be a new version of an existing data frame and what's not).
- Let agents put frames into the chat w/ minimal token cost (i.e.: `<data-frame name="..." />`)
- Investigate shortcomings of the "just SQL" approach and see if an approach using "sanitized but possibly unsafe python code" can be better.
  - See: https://github.com/Sema4AI/agent-platform/pull/794#issuecomment-3234347346 for use-cases to test.
- Create a full semantic data model (with metrics, facts, dimensions, etc.). Things to keep in mind:
  - For categorical columns, if there's a small set of allowed values, what are those values?
  - For numerical columns, some basic stats (like min/max/median sorta deal).
  - Semantic description of the columns.
- Update settings to use new settings flavor:
  See example: https://github.com/Sema4AI/agent-platform/blob/main/core/src/agent_platform/core/configurations/quotas.py
