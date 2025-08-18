import pytest


def check_upload_response(thread_response) -> str:
    from starlette.status import HTTP_200_OK

    assert thread_response.status_code == HTTP_200_OK, (
        f"File upload to thread: bad response: {thread_response.status_code} {thread_response.text}"
    )

    response_as_json = thread_response.json()
    assert len(response_as_json) == 1, "Expected exactly one file in the response"
    file_id = response_as_json[0]["file_id"]
    mime_type = response_as_json[0]["mime_type"]

    assert mime_type in (
        "text/csv",
        "text/tab-separated-values",
        "application/vnd.ms-excel",  # Even for a .csv this is what can be received in Windows.
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ), f"Unexpected mime type: {mime_type}"

    return file_id


@pytest.mark.integration
def test_data_frames_integration_multi_sheet(base_url_agent_server, datadir):
    from agent_platform.orchestrator.agent_server_client import AgentServerClient

    with AgentServerClient(base_url_agent_server) as agent_client:
        agent_id = agent_client.create_agent_and_return_agent_id(
            action_packages=[],
            platform_configs=[
                {
                    "kind": "openai",
                    "openai_api_key": "unused",
                    "models": {"openai": ["gpt-4.1"]},
                },
            ],
        )
        thread_id = agent_client.create_thread_and_return_thread_id(agent_id)

        thread_response = agent_client.upload_file_to_thread(
            thread_id,
            str(datadir / "sample.xlsx"),
            embedded=False,
        )

        file_id = check_upload_response(thread_response)

        # We should be able to inspect the file as a data frame (to get the sheets, columns and
        # even some sample data).
        found_data_frames = agent_client.inspect_file_as_data_frame(
            thread_id,
            file_id,
        )
        assert len(found_data_frames) == 2, "Expected exactly two data frames in the response"
        data_frame = found_data_frames[0]
        assert data_frame["sheet_name"] == "Sheet1"
        assert data_frame["name"] == "sample.xlsx"
        assert data_frame["num_rows"] == 2
        assert data_frame["num_columns"] == 2
        assert data_frame["column_headers"] == ["name", "age"]
        assert data_frame["sample_rows"] == [["John", 25], ["Jane", 30]]

        data_frame = found_data_frames[1]
        assert data_frame["sheet_name"] == "Sheet2"
        assert data_frame["name"] == "sample.xlsx"
        assert data_frame["num_rows"] == 2
        assert data_frame["num_columns"] == 2
        assert data_frame["column_headers"] == ["Name", "Location"]
        assert data_frame["sample_rows"] == [["John", "London"], ["Jane", "Australia"]]

        # And later if the inspection is fine, we can create a data frame from the file id
        # and sheet name.
        created = agent_client.create_data_frame_from_file(thread_id, file_id, sheet_name="Sheet1")
        assert created["sheet_name"] == "Sheet1"
        created = agent_client.create_data_frame_from_file(thread_id, file_id, sheet_name="Sheet2")
        assert created["sheet_name"] == "Sheet2"

        # Now, get the data frames in the thread
        data_frames = agent_client.get_data_frames(thread_id)
        assert len(data_frames) == 2, "Expected exactly one data frame in the response"
        assert {data_frame["name"] for data_frame in data_frames} == {
            "sample_sheet1",
            "sample_sheet2",
        }

        # Now, create a data frame from computation using both data frames (join by the name)
        data_frame_response = agent_client.create_data_frame_from_sql_computation(
            thread_id=thread_id,
            name="joined_data",
            description="Joined data from both sheets",
            sql_query="""
                SELECT * FROM sample_sheet1
                JOIN sample_sheet2 ON sample_sheet1.name = sample_sheet2.Name
            """,
        )
        assert data_frame_response["name"] == "joined_data"
        assert data_frame_response["num_rows"] == 2
        assert data_frame_response["num_columns"] == 4
        assert data_frame_response["column_headers"] == ["name", "age", "Name", "Location"]
        assert data_frame_response["data_frame_id"] is not None


@pytest.mark.integration
def test_data_frames_integration(base_url_agent_server):
    from agent_platform.orchestrator.agent_server_client import AgentServerClient

    with AgentServerClient(base_url_agent_server) as agent_client:
        agent_id = agent_client.create_agent_and_return_agent_id(
            action_packages=[],
            platform_configs=[
                {
                    "kind": "openai",
                    "openai_api_key": "unused",
                    "models": {"openai": ["gpt-4.1"]},
                },
            ],
        )
        thread_id = agent_client.create_thread_and_return_thread_id(agent_id)

        thread_response = agent_client.upload_file_to_thread(
            thread_id,
            "my-tabulated-data.csv",
            embedded=False,
            content=b"name,age\nJohn,25\nJane,30",
        )

        file_id = check_upload_response(thread_response)

        # We should be able to inspect the file as a data frame (to get the sheets, columns and
        # even some sample data).
        found_data_frames = agent_client.inspect_file_as_data_frame(
            thread_id,
            file_id,
        )
        assert len(found_data_frames) == 1, "Expected exactly one data frame in the response"
        data_frame = found_data_frames[0]
        assert data_frame["name"] == "my-tabulated-data.csv"
        assert data_frame["num_rows"] == 2
        assert data_frame["num_columns"] == 2
        assert data_frame["column_headers"] == ["name", "age"]
        assert data_frame["sample_rows"] == [["John", 25], ["Jane", 30]]

        # Just with 1 sample row now.
        found_data_frames = agent_client.inspect_file_as_data_frame(
            thread_id, file_id, num_samples=1
        )
        assert len(found_data_frames) == 1, "Expected exactly one data frame in the response"
        data_frame = found_data_frames[0]
        assert data_frame["name"] == "my-tabulated-data.csv"
        assert data_frame["num_rows"] == 2
        assert data_frame["num_columns"] == 2
        assert data_frame["column_headers"] == ["name", "age"]
        assert data_frame["sample_rows"] == [["John", 25]]

        # And later if the inspection is fine, we can create a data frame from the file id.
        data_frame_response = agent_client.create_data_frame_from_file(thread_id, file_id)
        assert data_frame_response["name"] == "my_tabulated_data"
        assert data_frame_response["num_rows"] == 2
        assert data_frame_response["num_columns"] == 2
        assert data_frame_response["column_headers"] == ["name", "age"]
        assert data_frame_response["data_frame_id"] is not None

        # Now, get the data frames in the thread
        data_frames = agent_client.get_data_frames(thread_id)
        assert len(data_frames) == 1, "Expected exactly one data frame in the response"
        data_frame = data_frames[0]
        assert data_frame["name"] == "my_tabulated_data"
        assert data_frame["num_rows"] == 2
        assert data_frame["num_columns"] == 2
        assert data_frame["column_headers"] == ["name", "age"]
        assert data_frame["data_frame_id"] == data_frame_response["data_frame_id"]


@pytest.mark.integration
def test_data_frames_computation_integration_success(base_url_agent_server):
    """Test creating a data frame from computation with valid SQL query."""
    from agent_platform.orchestrator.agent_server_client import AgentServerClient

    with AgentServerClient(base_url_agent_server) as agent_client:
        agent_id = agent_client.create_agent_and_return_agent_id(
            action_packages=[],
            platform_configs=[
                {
                    "kind": "openai",
                    "openai_api_key": "unused",
                    "models": {"openai": ["gpt-4.1"]},
                },
            ],
        )
        thread_id = agent_client.create_thread_and_return_thread_id(agent_id)

        # Upload a CSV file first
        thread_response = agent_client.upload_file_to_thread(
            thread_id,
            "my-data.csv",
            embedded=False,
            content=b"name,age,city\nJohn,25,New York\nJane,30,London\nBob,35,Paris",
        )

        file_id = check_upload_response(thread_response)

        # Create a data frame from the file
        agent_client.create_data_frame_from_file(thread_id, file_id, name="my_data")

        # Create a new data frame from computation
        computation_response = agent_client.create_data_frame_from_sql_computation(
            thread_id=thread_id,
            name="filtered_data",
            description="Filtered data for people over 25",
            # `my_data` can just be used directly as a table name (it's the name
            # of the data frame).
            sql_query="SELECT name, age FROM my_data WHERE age > 25",
        )

        # Verify the computation result
        assert computation_response["name"] == "filtered_data"
        assert computation_response["num_rows"] == 2  # Jane and Bob are over 25
        assert computation_response["num_columns"] == 2
        assert computation_response["column_headers"] == ["name", "age"]
        assert computation_response["data_frame_id"] is not None
        assert computation_response["description"] == "Filtered data for people over 25"

        # Verify the data frame appears in the thread
        data_frames = agent_client.get_data_frames(thread_id)
        assert len(data_frames) == 2, "Expected exactly two data frames in the response"

        # Find the computation data frame
        computation_df = None
        for df in data_frames:
            if df["name"] == "filtered_data":
                computation_df = df
                break

        assert computation_df is not None, "Computation data frame not found"
        assert computation_df["data_frame_id"] == computation_response["data_frame_id"]
