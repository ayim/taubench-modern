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

# Step 6 (current PR)

- Show sample data in the LLM summary

# Future work (not right now):

- Show column types in the LLM summary
- Don't remove tools after they were added into the context
- Let agents put frames into the chat w/ minimal token cost (i.e.: `<data-frame name="..." />`)
- Make the result of named queries (Tables) be available as data frames automatically.
- Allow the user to have data frames that are backed by a database.
- Investigate shortcomings of the "just SQL" approach and see if an approach using "sanitized but possibly unsafe python code" can be better.
  - See: https://github.com/Sema4AI/agent-platform/pull/794#issuecomment-3234347346 for use-cases to test.
- Create a data model. Things to keep in mind:
  - For categorical columns, if there's a small set of allowed values, what are those values?
  - For numerical columns, some basic stats (like min/max/median sorta deal).
  - Semantic description of the columns.
- Update settings to use new settings flavor:
  See example: https://github.com/Sema4AI/agent-platform/blob/main/core/src/agent_platform/core/configurations/quotas.py
