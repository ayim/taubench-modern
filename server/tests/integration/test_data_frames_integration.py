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
        data_frame_response = agent_client.create_data_frame_from_file(
            thread_id, file_id, sheet_name="Sheet2"
        )
        assert data_frame_response["name"] == "sample.xlsx"
        assert data_frame_response["num_rows"] == 2
        assert data_frame_response["num_columns"] == 2
        assert data_frame_response["column_headers"] == ["Name", "Location"]
        assert data_frame_response["data_frame_id"] is not None

        # Now, get the data frames in the thread
        data_frames = agent_client.get_data_frames(thread_id)
        assert len(data_frames) == 1, "Expected exactly one data frame in the response"
        data_frame = data_frames[0]
        assert data_frame["name"] == "sample.xlsx"
        assert data_frame["num_rows"] == 2
        assert data_frame["num_columns"] == 2
        assert data_frame["column_headers"] == ["Name", "Location"]
        assert data_frame["data_frame_id"] == data_frame_response["data_frame_id"]


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
        assert data_frame_response["name"] == "my-tabulated-data.csv"
        assert data_frame_response["num_rows"] == 2
        assert data_frame_response["num_columns"] == 2
        assert data_frame_response["column_headers"] == ["name", "age"]
        assert data_frame_response["data_frame_id"] is not None

        # Now, get the data frames in the thread
        data_frames = agent_client.get_data_frames(thread_id)
        assert len(data_frames) == 1, "Expected exactly one data frame in the response"
        data_frame = data_frames[0]
        assert data_frame["name"] == "my-tabulated-data.csv"
        assert data_frame["num_rows"] == 2
        assert data_frame["num_columns"] == 2
        assert data_frame["column_headers"] == ["name", "age"]
        assert data_frame["data_frame_id"] == data_frame_response["data_frame_id"]
