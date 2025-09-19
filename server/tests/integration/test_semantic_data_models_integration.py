"""Integration tests for semantic data model API endpoints."""

import pytest


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
            semantic_model=semantic_model,
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
            semantic_model=semantic_model,
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
            semantic_model=updated_semantic_model,
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
