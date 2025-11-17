Tasks:

1. We need to show information on how data frames were "assembled".

   This means that for a given data frame we need to collect:

   - The SQL query that was used to create the data frame.
   - Given that query, for each data frame referenced in the query,
     collect how it was assembled itself (so, it's a recursive process).

   Note: this is mostly already done in the DataFramesKernel class when
   doing the actual resolution, but now we need a way to collect the information
   instead of just computing the data frame and returning it.

   Implementation steps:

   `Step 1.1`. Provide a new API end point to collect the information.
   `/api/v2/threads/{thread_id}/data-frames/assembly-info`

   - The input should be a list of data frame names.
   - The output should be a markdown string of data frame assembly info.
     - The assembly info should contain:
       - Data frame name
       - SQL query that was used to create the data frame
       - For each table in the query that was used to create the data frame how it was assembled itself.
         - If it was a data frame, the data frame name use the same structure again
         - If it was a table in a semantic data model, either the data connection info or the file reference info.

   Note: for this step we just want the definition of the input and output, not the actual implementation (which
   at this point should just return dummy data).

   `Step 1.2`. Create a test case to test the new API endpoint (at this point, create the test
   to call that API endpoint, but don't just check that it returned an empty string, not its contents)

   Test case at: `server/tests/data_frames/test_data_frames_assembly_info.py`

   Create the test using the sqlite_storage fixture to store the model and the SampleModelCreator
   to create the base structure then create a thread with a semantic data model for a file in it
   and then create a data frame from that semantic data model and then call the API endpoint to get the assembly info.

   `Step 1.3`. Implement the actual logic to collect the information.

   - The logic should be implemented in the DataFramesKernel class.
   - The logic should be implemented in the `get_assembly_info` method.
   - The method should return a list of data frame assembly info.
   - The data frame assembly info should contain the SQL query that was used to create the data frame,
     the data frames that were used to create the data frame, and the assembly info for each of the data frames.

   `Step 1.4`. Update the UI to show the assembly info.

   - Note: we already have a button to download the CSV of a data frame, we need to add a button to download the assembly info.
     When the user clicks on the button to "show assembly info" for a data frame, we should call the new API endpoint to get the assembly
     info and then show the markdown in a modal.

2. We need to have a "Save Data Frame As Validated Query"

- Create a button to "Save As Validated Query in Semantic Data Model"

Behavior is:

- The "Save As Validated Query in Semantic Data Model" should be a button in the data frame view that allows the user to save the data frame as a named query, at this point it'll update the semantic data model with the new validated query.

We should start with the backend implementation.

`Step 2.1`. Create a new API end point to save the data frame as a validated query.

Endpoint: `/api/v2/threads/{thread_id}/data-frames/save-as-validated-query`
Receives the data frame name and the semantic data model id.

At that point it must:

- Get the data frame
- Get the semantic data model
- Add a section named `verified_queries` to the semantic data model

Format is:

```yaml
verified_queries:
  - name: 'data-frame-name'
    nlq: 'data-frame-description'
    verified_at: iso-date-time-string
    verified_by: user-id
    sql: 'full-data-frame-sql-query'
```

`Step 2.2`. Create a test case to test the new API endpoint (call the endpoint and
then check that the semantic data model was updated with the new validated query).

Note: create the test using the sqlite_storage fixture to store the model and the SampleModelCreator to create the base structure.

`Step 2.3`. When loading the data frame tools, also check the existing semantic data models. If there is any
verified query, add a tool to the data frame tools to create a data frame from the verified query.
The tool should be named `data_frames_create_from_verified_query` and should receive the name of the verified query as a parameter.
The data frame should be created from the SQL query in the verified query when called.

`Step 2.4`. Create an integration test that will create a semantic data model, data frame
and then call the API endpoint to save the data frame as a validated query and then
create a new thread in the same agent and ask it to create a new data frame based
on the verified query.
Verify that the new data frame was created successfully and that it has the correct contents.

Test case at: `server/tests/integration/test_semantic_data_models_integration.py`

`Step 2.5`. Update the UI to create a verified query from a data frame.

- Create a button to "Create Verified Query from Data Frame" in the data frame view that allows the user to create a verified query from the data frame.
- When the user clicks on the button to "Create Verified Query from Data Frame", we should call the new API endpoint to save the data frame as a validated query.

Note: the semantic data model id must be passed as a parameter to the `/save-as-validated-query` endpoint.
as such, the UI should list the available models to make the choice.
If there's no model available it should show a message asking the user to create a model to save the verified query in.
If there's only one model available it should automatically select it and save the verified query.
If there are multiple models available it should show a dropdown to select the model.

3. We need to be able to reference data frames in the Semantic Data Model.

Right now the `base_table` in the semantic data model can reference a data connection or a file reference.

We need to be able to reference a data frame in the semantic data model if there's no data_connection_id or file_reference.
`Step 3.1`: Implement what's outlined above.

`Step 3.2`: Create a test case to test the new functionality (create a semantic data model referencing a data frame, try to execute it and verify it fails, then add the data frame to the thread and verify it succeeds -- note that the query should reference the "logical name" of the table that should then be translated to the "real name" of the table which should be the data frame name).

4. Change UI used to edit the semantic data model so that we show 3 tabs:

`Tab 1` is the Business Context tab (right now it's a button which opens a dialog to edit the business context,
it should change so that it's a text area under the Business Context tab)
`Tab 2` is the semantic data model tab (right now this is the tree view of the semantic data model, it should
still be a tree view of the semantic data model as it is now, but should be under a tab called "Data Model")
`Tab 3` is a new tab showing the verified queries available in the semantic data model.
