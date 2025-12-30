"""Tests for agent package metadata generation.

This module tests the AgentMetadataGenerator class and its datasources extraction.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_platform.core.agent_package.metadata.action_packages import ActionPackageMetadataReader
from agent_platform.core.agent_package.metadata.agent_metadata_generator import (
    AgentMetadataGenerator,
)


class TestActionPackageMetadataReaderDatasources:
    """Tests for datasource extraction in ActionPackageMetadataReader."""

    @pytest.mark.asyncio
    async def test_extract_single_datasource(self):
        """Test extracting a single datasource from metadata."""
        action_package_path = "action-package-1"
        raw_metadata = {
            "metadata": {
                "data": {
                    "datasources": [
                        {
                            "name": "test_db",
                            "engine": "postgres",
                            "description": "Test PostgreSQL database",
                        }
                    ]
                }
            }
        }

        mock_handler = MagicMock()
        reader = ActionPackageMetadataReader(mock_handler)
        datasources = await reader.extract_datasources(action_package_path, raw_metadata)

        assert len(datasources) == 1
        assert datasources[0].customer_facing_name == "test_db"
        assert datasources[0].engine == "postgres"
        assert datasources[0].description == "Test PostgreSQL database"

    @pytest.mark.asyncio
    async def test_extract_multiple_datasources_from_single_action_package(self):
        """Test extracting multiple datasources from a single action package."""
        action_package_path = "action-package-1"
        raw_metadata = {
            "metadata": {
                "data": {
                    "datasources": [
                        {
                            "name": "db1",
                            "engine": "postgres",
                            "description": "First database",
                        },
                        {
                            "name": "db2",
                            "engine": "mysql",
                            "description": "Second database",
                        },
                    ]
                }
            }
        }

        mock_handler = MagicMock()
        reader = ActionPackageMetadataReader(mock_handler)
        datasources = await reader.extract_datasources(action_package_path, raw_metadata)

        assert len(datasources) == 2
        assert datasources[0].customer_facing_name == "db1"
        assert datasources[0].engine == "postgres"
        assert datasources[1].customer_facing_name == "db2"
        assert datasources[1].engine == "mysql"

    @pytest.mark.asyncio
    async def test_extract_datasources_from_multiple_action_packages(self):
        """Test extracting datasources from multiple action packages."""
        raw_metadata_by_path = {
            "action-package-1": {
                "metadata": {
                    "data": {
                        "datasources": [
                            {
                                "name": "db1",
                                "engine": "postgres",
                                "description": "From package 1",
                            }
                        ]
                    }
                }
            },
            "action-package-2": {
                "metadata": {
                    "data": {
                        "datasources": [
                            {
                                "name": "db2",
                                "engine": "mysql",
                                "description": "From package 2",
                            }
                        ]
                    }
                }
            },
        }

        mock_handler = MagicMock()
        reader = ActionPackageMetadataReader(mock_handler)
        datasources = []
        for action_package_path, raw_metadata in raw_metadata_by_path.items():
            datasources.extend(await reader.extract_datasources(action_package_path, raw_metadata))

        assert len(datasources) == 2
        names = {ds.customer_facing_name for ds in datasources}
        assert names == {"db1", "db2"}

    @pytest.mark.asyncio
    async def test_extract_deduplicates_datasources_with_same_name_and_engine(self):
        """Test that duplicate datasources with same name and engine are deduplicated.

        Note: Deduplication now happens at the AgentMetadataGenerator level when
        combining datasources from multiple action packages. Individual
        ActionPackageMetadataReader.extract_datasources calls only handle
        deduplication within a single action package.
        """
        # Test deduplication within a single action package
        action_package_path = "action-package-1"
        raw_metadata = {
            "metadata": {
                "data": {
                    "datasources": [
                        {
                            "name": "shared_db",
                            "engine": "postgres",
                            "description": "First occurrence",
                        },
                        {
                            "name": "shared_db",
                            "engine": "postgres",
                            "description": "Second occurrence (duplicate)",
                        },
                    ]
                }
            }
        }

        mock_handler = MagicMock()
        reader = ActionPackageMetadataReader(mock_handler)
        datasources = await reader.extract_datasources(action_package_path, raw_metadata)

        # Should only have one datasource (deduplicated)
        assert len(datasources) == 1
        assert datasources[0].customer_facing_name == "shared_db"
        assert datasources[0].engine == "postgres"

    @pytest.mark.asyncio
    async def test_extract_files_engine_uses_created_table_as_name(self):
        """Test that 'files' engine uses 'created_table' as the datasource name."""
        action_package_path = "action-package-1"
        raw_metadata = {
            "metadata": {
                "data": {
                    "datasources": [
                        {
                            "created_table": "my_file_table",
                            "engine": "files",
                            "description": "File-based datasource",
                            "file": "data/test.csv",
                        }
                    ]
                }
            }
        }

        mock_handler = MagicMock()
        reader = ActionPackageMetadataReader(mock_handler)
        datasources = await reader.extract_datasources(action_package_path, raw_metadata)

        assert len(datasources) == 1
        assert datasources[0].customer_facing_name == "my_file_table"
        assert datasources[0].engine == "files"
        # File path should be resolved to include the action package path
        assert "actions/action-package-1/data/test.csv" in datasources[0].configuration.get("file", "")

    @pytest.mark.asyncio
    async def test_extract_prediction_lightwood_engine_uses_model_name(self):
        """Test that 'prediction:lightwood' engine uses 'model_name' as the datasource name."""
        action_package_path = "action-package-1"
        raw_metadata = {
            "metadata": {
                "data": {
                    "datasources": [
                        {
                            "model_name": "my_prediction_model",
                            "engine": "prediction:lightwood",
                            "description": "Prediction model",
                        }
                    ]
                }
            }
        }

        mock_handler = MagicMock()
        reader = ActionPackageMetadataReader(mock_handler)
        datasources = await reader.extract_datasources(action_package_path, raw_metadata)

        assert len(datasources) == 1
        assert datasources[0].customer_facing_name == "my_prediction_model"
        assert datasources[0].engine == "prediction:lightwood"

    @pytest.mark.asyncio
    async def test_extract_empty_datasources(self):
        """Test extracting from metadata with no datasources."""
        action_package_path = "action-package-1"
        raw_metadata = {"metadata": {"data": {"datasources": []}}}

        mock_handler = MagicMock()
        reader = ActionPackageMetadataReader(mock_handler)
        datasources = await reader.extract_datasources(action_package_path, raw_metadata)

        assert len(datasources) == 0

    @pytest.mark.asyncio
    async def test_extract_missing_datasources_key(self):
        """Test extracting from metadata without datasources key."""
        action_package_path = "action-package-1"
        raw_metadata = {"metadata": {"data": {}}}

        mock_handler = MagicMock()
        reader = ActionPackageMetadataReader(mock_handler)
        datasources = await reader.extract_datasources(action_package_path, raw_metadata)

        assert len(datasources) == 0

    @pytest.mark.asyncio
    async def test_extract_missing_data_key(self):
        """Test extracting from metadata without data key."""
        action_package_path = "action-package-1"
        raw_metadata = {"metadata": {}}

        mock_handler = MagicMock()
        reader = ActionPackageMetadataReader(mock_handler)
        datasources = await reader.extract_datasources(action_package_path, raw_metadata)

        assert len(datasources) == 0


class TestAgentMetadataGeneratorDatasources:
    """Tests for datasource extraction in AgentMetadataGenerator."""

    @pytest.mark.asyncio
    async def test_generate_extracts_datasources_from_all_action_packages(self):
        """Test that generate() correctly extracts datasources from all action packages."""
        # Create mock agent package handler
        mock_agent_handler = MagicMock()
        mock_agent_handler.read_conversation_guide = AsyncMock(return_value=[])
        mock_agent_handler.load_agent_package_icon = AsyncMock(return_value="")
        mock_agent_handler.load_changelog = AsyncMock(return_value="")
        mock_agent_handler.load_readme = AsyncMock(return_value="")

        # Create mock agent spec
        mock_agent = MagicMock()
        mock_agent.name = "test-agent"
        mock_agent.version = "1.0.0"
        mock_agent.description = "Test agent"
        mock_agent.model = MagicMock()
        mock_agent.model.name = "gpt-4"
        mock_agent.model.provider = "openai"
        mock_agent.architecture = "agent"
        mock_agent.reasoning = "disabled"
        mock_agent.knowledge = []
        mock_agent.document_intelligence = None
        mock_agent.agent_settings = {}
        mock_agent.metadata = None
        mock_agent.selected_tools = None
        mock_agent.welcome_message = ""
        mock_agent.conversation_starter = ""
        mock_agent.action_packages = [
            MagicMock(path="action-package-1"),
            MagicMock(path="action-package-2"),
        ]
        mock_agent.mcp_servers = []
        mock_agent.docker_mcp_gateway = None

        mock_agent_handler.get_spec_agent = AsyncMock(return_value=mock_agent)

        # Create mock action package handlers with different datasources
        mock_ap_handler_1 = MagicMock()
        mock_ap_handler_1.read_metadata_dict = AsyncMock(
            return_value={
                "metadata": {
                    "data": {
                        "datasources": [
                            {
                                "name": "db_from_package_1",
                                "engine": "postgres",
                                "description": "Database from package 1",
                            }
                        ]
                    }
                }
            }
        )

        mock_ap_handler_2 = MagicMock()
        mock_ap_handler_2.read_metadata_dict = AsyncMock(
            return_value={
                "metadata": {
                    "data": {
                        "datasources": [
                            {
                                "name": "db_from_package_2",
                                "engine": "mysql",
                                "description": "Database from package 2",
                            }
                        ]
                    }
                }
            }
        )

        mock_agent_handler.get_action_packages_handlers = AsyncMock(
            return_value=[
                ("action-package-1", mock_ap_handler_1),
                ("action-package-2", mock_ap_handler_2),
            ]
        )

        generator = AgentMetadataGenerator(mock_agent_handler)

        # Mock the _process_action_packages to return empty list (focus on datasources)
        with patch.object(
            AgentMetadataGenerator, "_process_action_packages", new_callable=AsyncMock
        ) as mock_process_ap:
            mock_process_ap.return_value = []

            metadata = await generator.generate()

        # Verify datasources from both action packages are extracted
        assert len(metadata.datasources) == 2
        datasource_names = {ds.customer_facing_name for ds in metadata.datasources}
        assert datasource_names == {"db_from_package_1", "db_from_package_2"}

    @pytest.mark.asyncio
    async def test_generate_uses_correct_handler_for_each_action_package(self):
        """Test that each action package uses its own handler for metadata extraction."""
        # This test verifies the fix - previously the code was using the last handler
        # for all action packages due to a loop variable bug

        mock_agent_handler = MagicMock()
        mock_agent_handler.read_conversation_guide = AsyncMock(return_value=[])
        mock_agent_handler.load_agent_package_icon = AsyncMock(return_value="")
        mock_agent_handler.load_changelog = AsyncMock(return_value="")
        mock_agent_handler.load_readme = AsyncMock(return_value="")

        mock_agent = MagicMock()
        mock_agent.name = "test-agent"
        mock_agent.version = "1.0.0"
        mock_agent.description = "Test agent"
        mock_agent.model = MagicMock()
        mock_agent.model.name = "gpt-4"
        mock_agent.model.provider = "openai"
        mock_agent.architecture = "agent"
        mock_agent.reasoning = "disabled"
        mock_agent.knowledge = []
        mock_agent.document_intelligence = None
        mock_agent.agent_settings = {}
        mock_agent.metadata = None
        mock_agent.selected_tools = None
        mock_agent.welcome_message = ""
        mock_agent.conversation_starter = ""
        mock_agent.action_packages = [
            MagicMock(path="ap1"),
            MagicMock(path="ap2"),
            MagicMock(path="ap3"),
        ]
        mock_agent.mcp_servers = []
        mock_agent.docker_mcp_gateway = None

        mock_agent_handler.get_spec_agent = AsyncMock(return_value=mock_agent)

        # Create handlers with unique metadata to verify correct association
        handlers = []
        for i in range(1, 4):
            handler = MagicMock()
            handler.read_metadata_dict = AsyncMock(
                return_value={
                    "metadata": {
                        "data": {
                            "datasources": [
                                {
                                    "name": f"unique_ds_from_ap{i}",
                                    "engine": "postgres",
                                    "description": f"Datasource from action package {i}",
                                }
                            ]
                        }
                    }
                }
            )
            handlers.append((f"ap{i}", handler))

        mock_agent_handler.get_action_packages_handlers = AsyncMock(return_value=handlers)

        generator = AgentMetadataGenerator(mock_agent_handler)

        with patch.object(
            AgentMetadataGenerator, "_process_action_packages", new_callable=AsyncMock
        ) as mock_process_ap:
            mock_process_ap.return_value = []
            metadata = await generator.generate()

        # Verify all three unique datasources are present
        # If the bug existed (using last handler), we would only get one datasource
        assert len(metadata.datasources) == 3
        datasource_names = {ds.customer_facing_name for ds in metadata.datasources}
        assert datasource_names == {"unique_ds_from_ap1", "unique_ds_from_ap2", "unique_ds_from_ap3"}

        # Verify each handler's read_metadata_dict was called
        for _, handler in handlers:
            handler.read_metadata_dict.assert_called_once()
