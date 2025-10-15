"""Integration tests for semantic data model API endpoints."""

import pytest
from structlog import get_logger

logger = get_logger(__name__)


@pytest.mark.integration
def test_semantic_data_models_integration(base_url_agent_server, datadir, resources_dir):
    """Test semantic data model API endpoints integration."""
    from agent_platform.orchestrator.agent_server_client import AgentServerClient

    with AgentServerClient(base_url_agent_server) as agent_client:
        # Create an agent and thread
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

        db_file_1 = resources_dir / "data_frames" / "combined_data.sqlite"

        # Create data connections
        data_connection_1 = agent_client.create_data_connection(
            name="test-connection-1",
            description="Test connection 1",
            engine="sqlite",
            configuration={
                "db_file": str(db_file_1),
            },
        )

        name_file_1 = "hardware-and-energy-cost-to-train-notable-ai-systems.csv"
        file_1 = resources_dir / "data_frames" / name_file_1

        # Upload a file to the thread
        agent_client.upload_file_to_thread(
            thread_id,
            name_file_1,
            embedded=False,
            content=file_1.read_bytes(),
        )

        # Create a semantic data model
        semantic_model = {
            "name": "test_semantic_model",
            "description": "A test semantic model for integration testing",
            "tables": [
                {
                    "name": "hardware_and_energy_cost_to_train_notable_ai_systems",
                    "base_table": {
                        "table": "data_frame_hardware_and_energy_cost_to_train_notable_ai_systems",
                        "file_reference": {
                            "thread_id": thread_id,
                            "file_ref": name_file_1,
                            "sheet_name": "",
                        },
                    },
                    "dimensions": [
                        {
                            "name": "Entity",
                            "expr": "Entity",
                            "data_type": "TEXT",
                            "description": "The entity of the training datapoint",
                        },
                        {
                            "name": "Code",
                            "expr": "Code",
                            "data_type": "TEXT",
                            "description": "The code of the training datapoint",
                        },
                        {
                            "name": "Year",
                            "expr": "Year",
                            "data_type": "TEXT",
                            "description": "The year of the training datapoint",
                        },
                        {
                            "name": "Day",
                            "expr": "Day",
                            "data_type": "TEXT",
                            "description": "The day of the training datapoint",
                        },
                        {
                            "name": "Domain",
                            "expr": "Domain",
                            "data_type": "TEXT",
                            "description": "The domain of the training datapoint",
                        },
                        {
                            "name": "Cost (inflation-adjusted)",
                            "expr": "Cost (inflation-adjusted)",
                            "data_type": "TEXT",
                            "description": "The cost of the training datapoint",
                        },
                    ],
                },
                {
                    "name": "artificial_intelligence_number_training_datapoints",
                    "base_table": {
                        "database": "",  # Not required for SQLite
                        "schema": "",  # Not required for SQLite
                        "table": "artificial_intelligence_number_training_datapoints",
                        "data_connection_id": data_connection_1["id"],
                    },
                    "dimensions": [
                        {
                            "name": "Entity",
                            "expr": "Entity",
                            "data_type": "TEXT",
                            "description": "The entity of the training datapoint",
                        },
                        {
                            "name": "Code",
                            "expr": "Code",
                            "data_type": "TEXT",
                            "description": "The code of the training datapoint",
                        },
                        {
                            "name": "Day",
                            "expr": "Day",
                            "data_type": "TEXT",
                            "description": "The day of the training datapoint",
                        },
                        {
                            "name": "Training_dataset_size",
                            "expr": "Training_dataset_size",
                            "data_type": "INTEGER",
                            "description": "The size of the training dataset",
                        },
                        {
                            "name": "Domain",
                            "expr": "Domain",
                            "data_type": "TEXT",
                            "description": "The domain of the training datapoint",
                        },
                    ],
                },
            ],
        }

        # Create the semantic data model
        created_model_id_and_references = agent_client.create_semantic_data_model(
            dict(semantic_model=semantic_model),
        )
        assert semantic_model == agent_client.get_semantic_data_model(
            created_model_id_and_references["semantic_data_model_id"]
        )
        assert created_model_id_and_references["data_connection_ids"] == [data_connection_1["id"]]
        assert created_model_id_and_references["file_references"] == [
            {"thread_id": thread_id, "file_ref": name_file_1}
        ]

        # Test creating with a specific ID
        model_id = "test-model-id-123"
        created_model_with_id = agent_client.set_semantic_data_model(
            semantic_data_model_id=model_id,
            semantic_model=dict(semantic_model=semantic_model),
        )
        assert created_model_with_id["semantic_data_model_id"] == model_id
        assert created_model_with_id["data_connection_ids"] == [data_connection_1["id"]]
        assert created_model_with_id["file_references"] == [
            {"thread_id": thread_id, "file_ref": name_file_1}
        ]

        # Test getting the semantic data model
        retrieved_model = agent_client.get_semantic_data_model(model_id)
        assert retrieved_model == semantic_model

        # Test updating the semantic data model
        updated_semantic_model = semantic_model = {
            "name": "test_semantic_model",
            "description": "A test semantic model for integration testing",
            "tables": [
                {
                    "name": "hardware_and_energy_cost_to_train_notable_ai_systems",
                    "base_table": {
                        "table": "data_frame_hardware_and_energy_cost_to_train_notable_ai_systems",
                        "file_reference": {
                            "thread_id": thread_id,
                            "file_ref": name_file_1,
                            "sheet_name": "",
                        },
                    },
                    "dimensions": [
                        {
                            "name": "Entity",
                            "expr": "Entity",
                            "data_type": "TEXT",
                            "description": "The entity of the training datapoint",
                        },
                        {
                            "name": "Code",
                            "expr": "Code",
                            "data_type": "TEXT",
                            "description": "The code of the training datapoint",
                        },
                        {
                            "name": "Year",
                            "expr": "Year",
                            "data_type": "TEXT",
                            "description": "The year of the training datapoint",
                        },
                        {
                            "name": "Day",
                            "expr": "Day",
                            "data_type": "TEXT",
                            "description": "The day of the training datapoint",
                        },
                        {
                            "name": "Domain",
                            "expr": "Domain",
                            "data_type": "TEXT",
                            "description": "The domain of the training datapoint",
                        },
                        {
                            "name": "Cost (inflation-adjusted)",
                            "expr": "Cost (inflation-adjusted)",
                            "data_type": "TEXT",
                            "description": "The cost of the training datapoint",
                        },
                    ],
                },
            ],
        }

        # Test updating the semantic data model (leave just the file reference, not the connection)
        updated_model_id_and_references = agent_client.set_semantic_data_model(
            semantic_data_model_id=model_id,
            semantic_model=dict(semantic_model=updated_semantic_model),
        )
        assert updated_model_id_and_references["data_connection_ids"] == []
        assert updated_model_id_and_references["file_references"] == [
            {"thread_id": thread_id, "file_ref": name_file_1}
        ]
        assert updated_model_id_and_references["semantic_data_model_id"] == model_id

        # Verify the update
        retrieved_updated_model = agent_client.get_semantic_data_model(model_id)
        assert retrieved_updated_model == updated_semantic_model

        # Test deleting the semantic data model
        agent_client.delete_semantic_data_model(model_id)

        # Verify the model was deleted
        with pytest.raises(Exception, match="404"):
            agent_client.get_semantic_data_model(model_id)

        # Test deleting non-existent model
        with pytest.raises(Exception, match="404"):
            agent_client.delete_semantic_data_model("non-existent")

        # Test getting non-existent model
        with pytest.raises(Exception, match="404"):
            agent_client.get_semantic_data_model("non-existent")


@pytest.mark.integration
def test_semantic_data_model_query_with_llm_integration(
    base_url_agent_server, resources_dir, openai_api_key
):
    """Test semantic data model query with LLM integration."""
    from agent_platform.orchestrator.agent_server_client import AgentServerClient

    with AgentServerClient(base_url_agent_server) as agent_client:
        # Create an agent and thread
        agent_id = agent_client.create_agent_and_return_agent_id(
            action_packages=[],
            platform_configs=[
                {
                    "kind": "openai",
                    "openai_api_key": openai_api_key,
                    "models": {"openai": ["gpt-5-low"]},
                },
            ],
            runbook="""You are an agent which should make create data
            frames using the data_frames_create_from_sql tool,
            referencing the semantic data model that the user provides
            to answer user's questions.""",
            description="Agent which can query the semantic data model",
        )
        thread_id = agent_client.create_thread_and_return_thread_id(agent_id)

        # Setup data connection based on resources_dir / "data_frames" / "combined_data.sqlite"
        db_file_path = resources_dir / "data_frames" / "combined_data.sqlite"

        data_connection = agent_client.create_data_connection(
            name="test-connection-combined-data",
            description="Test connection for combined data",
            engine="sqlite",
            configuration={
                "db_file": str(db_file_path),
            },
        )

        # Inspect the connection
        inspect_response = agent_client.inspect_data_connection(
            connection_id=data_connection["id"],
        )

        # Verify inspection response has expected structure
        assert "tables" in inspect_response
        assert len(inspect_response["tables"]) > 0

        # Generate semantic data model from the connection
        generate_payload = {
            "name": "generated_semantic_model_integration",
            "description": "A generated semantic model for integration testing",
            "data_connections_info": [
                {
                    "data_connection_id": data_connection["id"],
                    "tables_info": inspect_response["tables"],
                }
            ],
            "files_info": [],
        }

        # Generate the semantic data model
        generated_model = agent_client.generate_semantic_data_model(generate_payload)
        assert "semantic_model" in generated_model

        # Create the semantic data model
        created_model = agent_client.create_semantic_data_model(generated_model)
        semantic_data_model_id = created_model["semantic_data_model_id"]

        # Set the generated data model for the agent
        agent_client.set_agent_semantic_data_models(agent_id, [semantic_data_model_id])

        # Verify the model was assigned to the agent
        agent_models = agent_client.get_agent_semantic_data_models(agent_id)
        assert len(agent_models) == 1
        assert semantic_data_model_id in agent_models[0]

        # Verify the model was created correctly
        retrieved_model = agent_client.get_semantic_data_model(semantic_data_model_id)
        assert retrieved_model == generated_model["semantic_model"]
        result, tool_calls = agent_client.send_message_to_agent_thread(
            agent_id,
            thread_id,
            (
                "Can you provide me with the list of notable AI systems which were "
                "sampled in the year 2023?"
            ),
        )
        for tool_call in tool_calls:
            if tool_call.tool_name == "data_frames_create_from_sql":
                break
        else:
            raise Exception("data_frames_create_from_sql tool call not found")

        result_found = str(result)
        assert "Claude 2" in result_found, "Claude 2 should be in the result"


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


@pytest.mark.integration
def test_generate_semantic_data_model_generation_integration(  # noqa: PLR0915
    base_url_agent_server, resources_dir, data_regression, openai_api_key
):
    """Test generate semantic data model API endpoint integration."""
    import copy

    import yaml
    from agent_platform.orchestrator.agent_server_client import AgentServerClient

    with AgentServerClient(base_url_agent_server) as agent_client:
        assert not agent_client.list_semantic_data_models(), (
            "No semantic data models should be present"
        )

        # Create an agent and thread
        agent_id = agent_client.create_agent_and_return_agent_id(
            action_packages=[],
            platform_configs=[
                {
                    "kind": "openai",
                    "openai_api_key": openai_api_key,
                    "models": {"openai": ["gpt-5-low"]},
                },
            ],
        )
        thread_id = agent_client.create_thread_and_return_thread_id(agent_id)

        db_file_1 = resources_dir / "data_frames" / "combined_data.sqlite"

        # Create data connections
        data_connection_1 = agent_client.create_data_connection(
            name="test-connection-1",
            description="Test connection 1",
            engine="sqlite",
            configuration={
                "db_file": str(db_file_1),
            },
        )

        # Inspect the data connection to get table/column info: In this case most of the info
        # is exactly what'll be expected to be passed to the generate semantic data model
        # API (in the UI this should be presented to the user as a list of tables/columns/sample
        # data to select from).
        inspect_response = agent_client.inspect_data_connection(
            connection_id=data_connection_1["id"],
        )
        data_regression.check(inspect_response, basename="data_connection_inspect_response")
        tables_info = inspect_response["tables"]
        for table_info in tables_info:
            assert "name" in table_info, "Table name is expected"
            assert "columns" in table_info, "Table columns are expected"
            assert "description" in table_info, "Table description is expected"
            assert "database" in table_info, "Table database is expected"
            assert "schema" in table_info, "Table schema is expected"
            for column_info in table_info["columns"]:
                assert "name" in column_info, "Column name is expected"
                assert "data_type" in column_info, "Column data type is expected"
                assert "sample_values" in column_info, "Column sample values are expected"

        # Upload a file to the thread
        name_file_1 = "hardware-and-energy-cost-to-train-notable-ai-systems.csv"
        file_1 = resources_dir / "data_frames" / name_file_1
        thread_response = agent_client.upload_file_to_thread(
            thread_id,
            name_file_1,
            embedded=False,
            content=file_1.read_bytes(),
        )
        file_id = check_upload_response(thread_response)
        found_data_frames = agent_client.inspect_file_as_data_frame(
            thread_id,
            file_id=file_id,
        )
        assert len(found_data_frames) == 1, "Expected exactly one data frame in the response"
        data_frame_info = next(iter(found_data_frames))

        # Delete fields that change on each run (so that the data_regression can be used to check
        # the expected results).
        assert "created_at" in data_frame_info, "Created at is expected"
        assert "file_id" in data_frame_info, "File id is expected"
        assert "thread_id" in data_frame_info, "Thread id is expected"
        data_frame_info["created_at"] = "<redacted>"
        data_frame_info["file_id"] = "<redacted>"
        data_frame_info["thread_id"] = "<redacted>"

        data_regression.check([data_frame_info], basename="file_data_frames")

        # Now, convert the data frame information to the expected table info to
        # generate the semantic data model.

        # That's all we get right now from the file inspection related to data
        # frame information (column names and sample values)
        column_headers = data_frame_info["column_headers"]
        # Note: the data-type is still not extracted in the file inspection right now
        # (so, use 'unknown' for the time being)
        column_infos = [{"name": column_name} for column_name in column_headers]
        sample_rows = data_frame_info["sample_rows"]

        # For a .csv it'll actually be None, but on a multi-sheet file it'll be the name of
        # the sheet.
        sheet_name = data_frame_info["sheet_name"]

        # Things are in a row-based format, so we need to convert them to a column-based format.
        for i in range(len(column_headers)):
            sample_value_for_column = [row[i] for row in sample_rows]
            column_infos[i]["sample_values"] = sample_value_for_column

        # Note: the name of the table here is "tricky" because it must be the name
        # of the data frame that'll be used later on!
        # At this point we're considering it to be `data_frame_1`, but this is
        # something that the user should select in the UI (and it needs to be
        # a valid variable name so that the sql can reference as a table later
        # on).
        file_tables_info = [
            {
                "name": "data_frame_1",
                "columns": column_infos,
                "database": None,
                "schema": None,
                "description": None,
            }
        ]

        # Generate semantic data model from the inspection results
        generate_payload = {
            "name": "generated_semantic_model",
            "description": "A generated semantic model for testing",
            "data_connections_info": [
                {
                    "data_connection_id": data_connection_1["id"],
                    "tables_info": inspect_response["tables"],
                }
            ],
            "files_info": [
                {
                    "thread_id": thread_id,
                    "file_ref": name_file_1,
                    "sheet_name": sheet_name,
                    "tables_info": file_tables_info,
                }
            ],
            "agent_id": agent_id,
        }

        # Generate the semantic data model
        generated_model = agent_client.generate_semantic_data_model(generate_payload)
        logger.info(f"Generated model:\n{yaml.safe_dump(generated_model)}")
        original_generated_model = copy.deepcopy(generated_model)

        semantic_model = generated_model["semantic_model"]

        # Redact the fields that change on each run (so that the data_regression can be used
        # to check the expected results).
        for table in semantic_model["tables"]:
            if "data_connection_id" in table["base_table"]:
                table["base_table"]["data_connection_id"] = "<redacted>"
            if "file_reference" in table["base_table"]:
                table["base_table"]["file_reference"]["thread_id"] = "<redacted>"
                table["base_table"]["file_reference"]["file_ref"] = "<redacted>"

        # We cannot use data_regression here as the generated model is different on each run
        # (as the LLM is used to enhance the model).
        # As such, just verify that the generated model tables/columns are present.
        assert "tables" in semantic_model, "Tables are expected"
        assert len(semantic_model["tables"]) > 0, "At least one table is expected"
        for table in semantic_model["tables"]:
            assert "name" in table, "Table name is expected"

        semantic_data_model_id = agent_client.create_semantic_data_model(original_generated_model)[
            "semantic_data_model_id"
        ]

        agent_client.set_agent_semantic_data_models(agent_id, [semantic_data_model_id])
        agent_client.set_thread_semantic_data_models(thread_id, [semantic_data_model_id])

        assert agent_client.get_thread_semantic_data_models(thread_id) == [
            {semantic_data_model_id: original_generated_model["semantic_model"]}
        ]

        assert agent_client.get_agent_semantic_data_models(agent_id) == [
            {semantic_data_model_id: original_generated_model["semantic_model"]}
        ]

        # Test the new list semantic data models API
        # List all semantic data models
        all_models = agent_client.list_semantic_data_models()
        assert len(all_models) == 1
        assert all_models[0]["semantic_data_model_id"] == semantic_data_model_id
        assert all_models[0]["agent_ids"] == [agent_id]
        assert all_models[0]["thread_ids"] == [thread_id]
        assert all_models[0]["data_connection_ids"] == [data_connection_1["id"]]


@pytest.mark.integration
def test_semantic_data_model_with_file_reference_workflow(base_url_agent_server, openai_api_key):
    """Create semantic data model from file, upload file, and query with LLM."""
    from agent_platform.orchestrator.agent_server_client import AgentServerClient

    from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel

    with AgentServerClient(base_url_agent_server) as agent_client:
        # Step 1: Create a CSV file in memory
        csv_content = """Entity,Year,Cost
OpenAI,2023,10
Anthropic,2023,20
Google,2023,15"""

        # Step 2: Use the API to inspect the file in-memory to extract contents
        # as if it was a database
        inspect_response = agent_client.inspect_file_as_data_connection(
            file_contents=csv_content.encode("utf-8"), file_name="test-ai-systems.csv"
        )

        # Verify inspection response has expected structure
        assert "tables" in inspect_response
        assert len(inspect_response["tables"]) == 1
        table_info = inspect_response["tables"][0]
        assert table_info["name"] == "test-ai-systems.csv"
        assert len(table_info["columns"]) == 3  # Entity, Year, Cost

        # Step 3: Create a semantic data model from it
        semantic_model: SemanticDataModel = {
            "name": "test_ai_systems_semantic_model",
            "description": "A test semantic model for AI systems data",
            "tables": [
                {
                    "name": "ai_systems_data",
                    "base_table": {
                        # This will be the data frame name (use to reference the table in the
                        # SQL queries)
                        "table": "data_frame_test_ai_systems",
                        # Because we're uploading the semantic data model to an agent, we don't
                        # know the thread_id or file_ref yet, so we leave them empty. Later
                        # on we must automatically match with a matching file uploaded to the
                        # thread.
                        "file_reference": {
                            "thread_id": "",
                            "file_ref": "",
                            "sheet_name": "",
                        },
                    },
                    "dimensions": [
                        {
                            "name": "Entity",
                            "expr": "Entity",
                            "data_type": "TEXT",
                            "description": "The entity of the AI system",
                        },
                        {
                            "name": "Year",
                            "expr": "Year",
                            "data_type": "TEXT",
                            "description": "The year of the AI system",
                        },
                        {
                            "name": "Cost",
                            "expr": "Cost",
                            "data_type": "NUMBER",
                            "description": "The cost of the AI system",
                        },
                    ],
                },
            ],
        }

        # Step 4: Create a new thread
        agent_id = agent_client.create_agent_and_return_agent_id(
            action_packages=[],
            platform_configs=[
                {
                    "kind": "openai",
                    "openai_api_key": openai_api_key,
                    "models": {"openai": ["gpt-4o-mini"]},
                },
            ],
            runbook=(
                "You are an agent which should create data frames using the "
                "data_frames_create_from_sql tool, referencing the semantic data model "
                "that the user provides to answer user's questions."
            ),
            description="Agent which can query the semantic data model",
        )

        # Create the semantic data model -- note that it doesn't really reference
        # a file yet (because it currently doesn't exist in a thread).
        created_model = agent_client.create_semantic_data_model(
            dict(semantic_model=semantic_model),
        )
        semantic_data_model_id = created_model["semantic_data_model_id"]

        # Set the semantic data model for the agent
        agent_client.set_agent_semantic_data_models(agent_id, [semantic_data_model_id])

        thread_id = agent_client.create_thread_and_return_thread_id(agent_id)

        # Step 5: Upload that file to the thread
        thread_response = agent_client.upload_file_to_thread(
            thread_id,
            "test-ai-systems.csv",
            embedded=False,
            content=csv_content.encode("utf-8"),
        )
        check_upload_response(thread_response)

        # Step 7: Actually ask the LLM which semantic data models it has available
        result, _tool_calls = agent_client.send_message_to_agent_thread(
            agent_id,
            thread_id,
            "What semantic data models do you have available?",
        )

        # Verify that the agent can access the semantic data model
        result_text = str(result)
        assert "test_ai_systems_semantic_model" in result_text or "ai_systems_data" in result_text

        result, tool_calls = agent_client.send_message_to_agent_thread(
            agent_id,
            thread_id,
            "Please create a data frame from the AI systems table showing entity, year and cost.",
        )
        result_text = str(result)
        assert "data_frames_create_from_sql" in str(tool_calls)
        assert "Data frame" in str(tool_calls)
        assert "created from SQL query" in str(tool_calls)
