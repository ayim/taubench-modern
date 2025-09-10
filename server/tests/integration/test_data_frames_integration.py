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
        "application/vnd.oasis.opendocument.spreadsheet",  # open office (.ods)
    ), f"Unexpected mime type: {mime_type}"

    return file_id


# Convert bytes to base64 for JSON serialization (the parquet_contents is a bytes object)
def convert_bytes_to_base64(obj):
    import base64

    if isinstance(obj, bytes):
        return base64.b64encode(obj).decode("utf-8")
    elif isinstance(obj, dict):
        return {k: convert_bytes_to_base64(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_bytes_to_base64(item) for item in obj]
    else:
        return obj


def remove_changed_fields(data_frame_response):
    data_frame_response.pop("thread_id", None)
    data_frame_response.pop("created_at", None)
    data_frame_response.pop("file_id", None)
    data_frame_response.pop("data_frame_id", None)


def _upload_file_to_thread(agent_client, thread_id, file):
    thread_response = agent_client.upload_file_to_thread(
        thread_id,
        str(file),
        embedded=False,
    )
    file_id = check_upload_response(thread_response)
    found_data_frames = agent_client.inspect_file_as_data_frame(
        thread_id,
        file_id=file_id,
    )
    return file_id, found_data_frames


@pytest.mark.integration
def test_data_frames_integration_with_date(base_url_agent_server, datadir, file_regression):
    import json

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

        file_id_ods, found_data_frames = _upload_file_to_thread(
            agent_client, thread_id, datadir / "example.ods"
        )
        assert len(found_data_frames) == 1, "Expected exactly one data frame in the response"

        created = agent_client.create_data_frame_from_file(
            thread_id, file_id_ods, sheet_name="Sheet1"
        )
        assert created["sheet_name"] == "Sheet1"
        remove_changed_fields(created)
        file_regression.check(
            json.dumps(convert_bytes_to_base64(created), indent=2), basename="created_sheet1_ods"
        )

        # Now, create a data frame from computation using both data frames (join by the name)
        agent_client.create_data_frame_from_sql_computation(
            thread_id=thread_id,
            name="cloned_sheet1",
            description="Cloned sheet1",
            sql_query=f"""
                SELECT * FROM {created["name"]}
            """,
        )

        # Now, get the data frames in the thread
        data_frames = agent_client.get_data_frames(thread_id, num_samples=2)
        assert len(data_frames) == 2
        data_frame_cloned_sheet1 = next(df for df in data_frames if df["name"] == "cloned_sheet1")
        remove_changed_fields(data_frame_cloned_sheet1)
        file_regression.check(
            json.dumps(convert_bytes_to_base64(data_frame_cloned_sheet1), indent=2),
            basename="cloned_sheet1",
        )

        contents = agent_client.get_data_frame_contents(
            thread_id,
            data_frame_name="cloned_sheet1",
            column_names=["segment", "country", "units sold"],
        )
        assert contents is not None
        assert json.loads(contents) == [
            {
                "Segment": "Public",
                "Country": "Portugal",
                "Units Sold": 1500.5,
            },
            {
                "Segment": "Private",
                "Country": "Italy",
                "Units Sold": 1500.3,
            },
        ]


@pytest.mark.integration
def test_data_frames_integration_multi_sheet(base_url_agent_server, datadir, file_regression):
    import json

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
        file_id_xlsx, found_data_frames = _upload_file_to_thread(
            agent_client, thread_id, datadir / "sample.xlsx"
        )

        # We should be able to inspect the file as a data frame (to get the sheets, columns and
        # even some sample data).
        assert len(found_data_frames) == 2, "Expected exactly two data frames in the response"
        data_frame = found_data_frames[0]
        assert data_frame["sheet_name"] == "Sheet1"
        remove_changed_fields(data_frame)
        file_regression.check(
            json.dumps(convert_bytes_to_base64(data_frame), indent=2), basename="inspect_sheet1"
        )

        data_frame = found_data_frames[1]
        assert data_frame["sheet_name"] == "Sheet2"
        remove_changed_fields(data_frame)
        file_regression.check(
            json.dumps(convert_bytes_to_base64(data_frame), indent=2), basename="inspect_sheet2"
        )

        # And later if the inspection is fine, we can create a data frame from the file id
        # and sheet name.
        created = agent_client.create_data_frame_from_file(
            thread_id, file_id_xlsx, sheet_name="Sheet1"
        )
        assert created["sheet_name"] == "Sheet1"
        remove_changed_fields(created)
        file_regression.check(
            json.dumps(convert_bytes_to_base64(created), indent=2), basename="created_sheet1"
        )

        created = agent_client.create_data_frame_from_file(
            thread_id, file_id_xlsx, sheet_name="Sheet2"
        )
        assert created["sheet_name"] == "Sheet2"
        remove_changed_fields(created)
        file_regression.check(
            json.dumps(convert_bytes_to_base64(created), indent=2), basename="created_sheet2"
        )

        with pytest.raises(
            Exception, match="Multiple data frames found in file. Please specify sheet_name."
        ):
            agent_client.create_data_frame_from_file(thread_id, file_id_xlsx)

        # Now, get the data frames in the thread
        data_frames = agent_client.get_data_frames(thread_id, num_samples=2)
        assert len(data_frames) == 2, "Expected exactly one data frame in the response"
        assert {data_frame["name"] for data_frame in data_frames} == {
            "sample_sheet1",
            "sample_sheet2",
        }
        assert data_frames[0]["sample_rows"] == [["John", 25], ["Jane", 30]]
        assert data_frames[1]["sample_rows"] == [["John", "London"], ["Jane", "Australia"]]

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
        remove_changed_fields(data_frame_response)
        file_regression.check(
            json.dumps(convert_bytes_to_base64(data_frame_response), indent=2),
            basename="joined_data",
        )


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
            file_ref="my-tabulated-data.csv",  # With name
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
            thread_id,
            file_id=file_id,
            num_samples=1,
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

        # Get the full data in parquet format
        slice_response = agent_client.get_data_frame_slice(
            thread_id,
            data_frame["data_frame_id"],
            output_format="parquet",
            order_by="aGe",
        )
        assert slice_response is not None

        import io

        import pyarrow.parquet as pq

        table = pq.read_table(io.BytesIO(slice_response))
        assert table.column_names == ["name", "age"]
        assert table.to_pylist() == [{"name": "John", "age": 25}, {"name": "Jane", "age": 30}]

        # Get the full data in parquet format in descending order
        slice_response = agent_client.get_data_frame_slice(
            thread_id,
            data_frame["data_frame_id"],
            output_format="parquet",
            order_by="-aGe",
        )
        assert slice_response is not None

        table = pq.read_table(io.BytesIO(slice_response))
        assert table.column_names == ["name", "age"]
        assert table.to_pylist() == [{"name": "Jane", "age": 30}, {"name": "John", "age": 25}]


@pytest.mark.integration
def test_data_frames_computation_integration_success(
    base_url_agent_server_with_data_frames, openai_api_key
):
    """Test creating a data frame from computation with valid SQL query."""
    import json

    from agent_platform.orchestrator.agent_server_client import AgentServerClient

    with AgentServerClient(base_url_agent_server_with_data_frames) as agent_client:
        agent_id = agent_client.create_agent_and_return_agent_id(
            action_packages=[],
            platform_configs=[
                {
                    "kind": "openai",
                    "openai_api_key": openai_api_key,
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
        created = agent_client.create_data_frame_from_file(thread_id, file_id, name="my_data")

        # Request a slice of the data frame
        slice_response = agent_client.get_data_frame_slice(
            thread_id,
            created["data_frame_id"],
            offset=0,
            limit=2,
            output_format="json",
        )

        loaded = json.loads(slice_response)
        assert loaded == [
            {"name": "John", "age": 25, "city": "New York"},
            {"name": "Jane", "age": 30, "city": "London"},
        ]

        # Request just the name and city
        slice_response = agent_client.get_data_frame_slice(
            thread_id,
            created["data_frame_id"],
            offset=1,
            limit=1,
            output_format="json",
            column_names=["nAme", "ciTy"],  # case should not matter
        )

        loaded = json.loads(slice_response)
        assert loaded == [{"name": "Jane", "city": "London"}]

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

        # Get all data from the computation data frame
        slice_response = agent_client.get_data_frame_slice(
            thread_id,
            computation_df["data_frame_id"],
            output_format="json",
        )

        loaded = json.loads(slice_response)
        assert loaded == [{"name": "Jane", "age": 30}, {"name": "Bob", "age": 35}]

        # Now request just the name and 1st row
        slice_response = agent_client.get_data_frame_slice(
            thread_id,
            computation_df["data_frame_id"],
            output_format="json",
            column_names=["nAMe"],  # case should not matter
            limit=1,
        )

        loaded = json.loads(slice_response)
        assert loaded == [{"name": "Jane"}]

        # Now request just the age in 2nd row
        slice_response = agent_client.get_data_frame_slice(
            thread_id,
            computation_df["data_frame_id"],
            output_format="json",
            column_names=["age"],
            offset=1,
            limit=1,
        )

        loaded = json.loads(slice_response)
        assert loaded == [{"age": 35}]

        result, tool_calls = agent_client.send_message_to_agent_thread(
            agent_id,
            thread_id,
            "Can you let me know what data frames you have?",
        )
        result_found = str(result)

        if "my_data" not in result_found.lower() and "filtered_data" not in result_found.lower():
            raise Exception("Data frames not found in the response. Found: " + result_found)
