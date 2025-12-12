"""Tests for SQL generation helper functions in server/kernel/sql.py."""

from datetime import UTC, datetime
from tempfile import SpooledTemporaryFile
from typing import Any, BinaryIO, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from agent_platform.core.agent import Agent, AgentArchitecture
from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel
from agent_platform.core.data_frames.semantic_data_model_validation import (
    References,
    _FileReference,
)
from agent_platform.core.files import UploadedFile
from agent_platform.core.payloads import UploadFilePayload
from agent_platform.core.runbook import Runbook
from agent_platform.core.thread import Thread
from agent_platform.server.file_manager.option import FileManagerService
from agent_platform.server.kernel.sql import (
    AgenticSqlStrategy,
    LegacySqlStrategy,
    _collect_sdm_files,
    _create_internal_tool_response_from_sql_thread,
    _find_sdm_by_name,
    _upload_sdm_files,
)

pytest_plugins = ["server.tests.storage_fixtures"]

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def mock_storage():
    """Create a mock storage instance for testing."""
    storage = AsyncMock()
    return storage


@pytest.fixture
def mock_kernel():
    """Create a mock kernel with all necessary attributes for testing."""
    kernel = MagicMock()

    # Mock user
    kernel.user.user_id = "test-user-123"

    # Mock thread
    kernel.thread.thread_id = "test-thread-456"

    # Mock agent
    kernel.agent.platform_configs = {"openai": {"api_key": "test-key"}}
    kernel.agent.agent_architecture = "experimental"

    return kernel


@pytest.fixture
def sample_sdms() -> list[dict[str, Any]]:
    """Sample semantic data models for testing."""
    return [
        {
            "id": "sdm-001",
            "name": "sales_data",
            "description": "Sales data model",
            "tables": [],
        },
        {
            "id": "sdm-002",
            "name": "customer_data",
            "description": "Customer data model",
            "tables": [],
        },
        {
            "id": "sdm-003",
            "name": "inventory_data",
            "description": "Inventory data model",
            "tables": [],
        },
    ]


@pytest.fixture
def mock_data_frame_tools():
    """Create a mock data frame tools instance."""
    return MagicMock()


@pytest.fixture
def simple_sdm_with_engine() -> tuple[SemanticDataModel, str]:
    """A simple semantic data model with DuckDB engine."""
    return cast(
        tuple[SemanticDataModel, str],
        (
            {
                "name": "test_model",
                "description": "A test model",
                "tables": [
                    {
                        "name": "users",
                        "description": "User table",
                        "dimensions": [
                            {"name": "user_id", "expr": "user_id", "data_type": "INTEGER"},
                            {"name": "username", "expr": "username", "data_type": "VARCHAR"},
                        ],
                    }
                ],
            },
            "duckdb",
        ),
    )


@pytest.fixture
def snowflake_sdm_with_variant() -> tuple[SemanticDataModel, str]:
    """Snowflake SDM with VARIANT columns."""
    return cast(
        tuple[SemanticDataModel, str],
        (
            {
                "name": "snowflake_products",
                "tables": [
                    {
                        "name": "products",
                        "dimensions": [
                            {"name": "product_id", "expr": "product_id", "data_type": "INTEGER"},
                            {"name": "metadata", "expr": "metadata", "data_type": "VARIANT"},
                        ],
                    }
                ],
            },
            "snowflake",
        ),
    )


@pytest.mark.asyncio
async def test_finds_sdm_by_exact_name_match(mock_storage, sample_sdms):
    """Should successfully find SDM when name matches exactly."""
    # Arrange
    agent_id = "agent-123"
    sdm_name = "customer_data"

    # Mock storage to return SDM IDs and then the SDM data
    mock_storage.get_agent_semantic_data_model_ids.return_value = [
        "sdm-001",
        "sdm-002",
        "sdm-003",
    ]
    mock_storage.get_semantic_data_model.side_effect = sample_sdms

    # Act
    result = await _find_sdm_by_name(mock_storage, agent_id, sdm_name)

    # Assert
    assert result is not None
    sdm_id, target_sdm = result
    assert sdm_id == "sdm-002"
    mock_storage.get_agent_semantic_data_model_ids.assert_called_once_with(agent_id)
    assert mock_storage.get_semantic_data_model.call_count == 2


@pytest.mark.asyncio
async def test_returns_none_when_sdm_name_not_found(mock_storage, sample_sdms):
    """Should return None when no SDM matches the requested name."""
    # Arrange
    agent_id = "agent-123"
    sdm_name = "nonexistent_model"

    mock_storage.get_agent_semantic_data_model_ids.return_value = [
        "sdm-001",
        "sdm-002",
        "sdm-003",
    ]
    mock_storage.get_semantic_data_model.side_effect = sample_sdms

    # Act
    result = await _find_sdm_by_name(mock_storage, agent_id, sdm_name)

    # Assert
    assert result is None
    assert mock_storage.get_semantic_data_model.call_count == 3


@pytest.mark.asyncio
async def test_returns_correct_sdm_when_multiple_exist(mock_storage, sample_sdms):
    """Should return the correct SDM ID when multiple SDMs exist."""
    # Arrange
    agent_id = "agent-123"
    sdm_name = "sales_data"

    mock_storage.get_agent_semantic_data_model_ids.return_value = [
        "sdm-001",
        "sdm-002",
        "sdm-003",
    ]
    mock_storage.get_semantic_data_model.side_effect = sample_sdms

    # Act
    result = await _find_sdm_by_name(mock_storage, agent_id, sdm_name)

    # Assert
    assert result is not None
    sdm_id, target_sdm = result
    assert sdm_id == "sdm-001"
    mock_storage.get_semantic_data_model.assert_called_once_with("sdm-001")


@pytest.mark.asyncio
async def test_handles_empty_sdm_list(mock_storage):
    """Should return None when agent has no SDMs."""
    # Arrange
    agent_id = "agent-123"
    sdm_name = "any_model"

    mock_storage.get_agent_semantic_data_model_ids.return_value = []

    # Act
    result = await _find_sdm_by_name(mock_storage, agent_id, sdm_name)

    # Assert
    assert result is None
    mock_storage.get_agent_semantic_data_model_ids.assert_called_once_with(agent_id)
    mock_storage.get_semantic_data_model.assert_not_called()


@pytest.mark.asyncio
async def test_handles_sdm_with_missing_name_field(mock_storage):
    """Should handle SDMs that don't have a 'name' field."""
    # Arrange
    agent_id = "agent-123"
    sdm_name = "test_model"

    mock_storage.get_agent_semantic_data_model_ids.return_value = [
        "sdm-001",
        "sdm-002",
        "sdm-003",
    ]

    # Some SDMs missing the 'name' field, last one has it
    mock_storage.get_semantic_data_model.side_effect = [
        {"id": "sdm-001", "description": "No name field"},
        {"id": "sdm-002"},  # No name field
        {"id": "sdm-003", "name": "test_model"},
    ]

    # Act
    result = await _find_sdm_by_name(mock_storage, agent_id, sdm_name)

    # Assert
    assert result is not None
    sdm_id, target_sdm = result
    assert sdm_id == "sdm-003"
    assert mock_storage.get_semantic_data_model.call_count == 3


@pytest.mark.asyncio
async def test_handles_sdm_with_none_name(mock_storage):
    """Should handle SDMs where 'name' field is None."""
    # Arrange
    agent_id = "agent-123"
    sdm_name = "valid_model"

    mock_storage.get_agent_semantic_data_model_ids.return_value = [
        "sdm-001",
        "sdm-002",
    ]

    mock_storage.get_semantic_data_model.side_effect = [
        {"id": "sdm-001", "name": None},  # None name
        {"id": "sdm-002", "name": "valid_model"},
    ]

    # Act
    result = await _find_sdm_by_name(mock_storage, agent_id, sdm_name)

    # Assert
    assert result is not None
    sdm_id, target_sdm = result
    assert sdm_id == "sdm-002"


class TestLegacySqlStrategy:
    """Tests for LegacySqlStrategy.get_context_additions method."""

    @pytest.fixture
    def strategy(self, mock_data_frame_tools):
        """Create a LegacySqlStrategy instance for testing."""
        return LegacySqlStrategy(data_frame_tools=mock_data_frame_tools)

    def test_returns_empty_string_for_empty_models_list(self, strategy):
        """Should return empty string when no models are provided."""
        # Act
        result = strategy.get_context_additions([])

        # Assert
        assert result == ""

    def test_includes_sql_generation_instructions(self, strategy, simple_sdm_with_engine):
        """Should include SQL generation instructions for Legacy strategy."""
        # Act
        result = strategy.get_context_additions([simple_sdm_with_engine])

        # Assert
        # Legacy strategy includes SQL syntax rules
        assert "SQL SYNTAX RULES" in result or "FROM my_table" in result

    def test_includes_sdm_summary(self, strategy, simple_sdm_with_engine):
        """Should include semantic data model summary."""
        # Act
        result = strategy.get_context_additions([simple_sdm_with_engine])

        # Assert
        # Should contain the model name and table name
        assert "test_model" in result
        assert "users" in result

    def test_includes_snowflake_variant_guidance_for_snowflake_models(
        self, strategy, snowflake_sdm_with_variant
    ):
        """Should include Snowflake VARIANT guidance for Snowflake databases."""
        # Act
        result = strategy.get_context_additions([snowflake_sdm_with_variant])

        # Assert
        # Should have Snowflake-specific VARIANT guidance
        assert "SNOWFLAKE" in result or "VARIANT" in result
        assert "bracket notation" in result.lower() or "col['field']" in result

    def test_handles_multiple_models(
        self, strategy, simple_sdm_with_engine, snowflake_sdm_with_variant
    ):
        """Should handle multiple semantic data models."""
        # Act
        result = strategy.get_context_additions(
            [simple_sdm_with_engine, snowflake_sdm_with_variant]
        )

        # Assert
        # Should contain both model names
        assert "test_model" in result
        assert "snowflake_products" in result


class TestAgenticSqlStrategy:
    """Tests for AgenticSqlStrategy."""

    @pytest.fixture
    def strategy(self, mock_data_frame_tools):
        """Create an AgenticSqlStrategy instance for testing."""
        return AgenticSqlStrategy(data_frame_tools=mock_data_frame_tools)

    # ========================================================================
    # get_context_additions tests
    # ========================================================================

    def test_returns_empty_string_for_empty_models_list(self, strategy):
        """Should return empty string when no models are provided."""
        # Act
        result = strategy.get_context_additions([])

        # Assert
        assert result == ""

    def test_includes_sdm_summary(self, strategy, simple_sdm_with_engine):
        """Should include semantic data model summary."""
        # Act
        result = strategy.get_context_additions([simple_sdm_with_engine])

        # Assert
        # Should contain the model name
        assert "test_model" in result

    def test_includes_coaching_on_generate_sql_usage(self, strategy, simple_sdm_with_engine):
        """Should include coaching on how to use generate_sql tool."""
        # Act
        result = strategy.get_context_additions([simple_sdm_with_engine])

        # Assert
        # Should mention the generate_sql tool
        assert "generate_sql" in result
        # Should mention choosing semantic data model
        assert "Choose Semantic Data Model" in result or "Semantic Data Model" in result

    def test_includes_coaching_on_create_data_frame_from_sql_usage(
        self, strategy, simple_sdm_with_engine
    ):
        """Should include coaching on when to use create_data_frame_from_sql."""
        # Act
        result = strategy.get_context_additions([simple_sdm_with_engine])

        # Assert
        # Should mention the data_frames_create_from_sql tool (the actual tool name)
        assert "data_frames_create_from_sql" in result

    def test_does_not_include_sql_syntax_instructions(self, strategy, simple_sdm_with_engine):
        """Should NOT include SQL syntax instructions (delegated to sub-agent)."""
        # Act
        result = strategy.get_context_additions([simple_sdm_with_engine])

        # Assert
        # Should NOT have SQL syntax rules (those go to the sub-agent)
        assert "SQL SYNTAX RULES" not in result

    def test_does_not_include_snowflake_variant_guidance(
        self, strategy, snowflake_sdm_with_variant
    ):
        """Should NOT include Snowflake VARIANT guidance (delegated to sub-agent)."""
        # Act
        result = strategy.get_context_additions([snowflake_sdm_with_variant])

        # Assert
        # Should NOT have Snowflake-specific syntax guidance
        # (The banner and detailed VARIANT instructions should not be in parent agent context)
        assert "🚨 CRITICAL: SNOWFLAKE VARIANT" not in result

    def test_includes_status_handling_coaching(self, strategy, simple_sdm_with_engine):
        """Should include coaching on handling different status responses."""
        # Act
        result = strategy.get_context_additions([simple_sdm_with_engine])

        # Assert
        # Should mention different status codes
        assert "success" in result.lower()
        assert "needs_info" in result.lower() or "clarification" in result.lower()
        assert "failure" in result.lower()


@pytest.mark.asyncio
async def test_create_internal_tool_response_from_sql_thread(sqlite_storage, tmp_path):
    """Test that helper function creates InternalToolResponse with correct metadata structure."""
    import hashlib

    from agent_platform.core.thread import Thread, ThreadAgentMessage, ThreadTextContent
    from agent_platform.core.thread.content.sql_generation import (
        SQLGenerationContent,
        SQLGenerationDetails,
        SQLGenerationStatus,
    )

    # Get user
    user, _ = await sqlite_storage.get_or_create_user(sub="test-user")

    # Create an agent
    from agent_platform.core.agent import Agent
    from agent_platform.core.agent.agent_architecture import AgentArchitecture
    from agent_platform.core.runbook import Runbook

    agent = Agent(
        name="Test Agent",
        description="Test agent for SQL generation",
        user_id=user.user_id,
        runbook_structured=Runbook(raw_text="test", content=[]),
        version="1.0.0",
        platform_configs=[],
        agent_architecture=AgentArchitecture(name="default", version="1.0.0"),
    )
    await sqlite_storage.upsert_agent(user.user_id, agent)

    # Create a thread with messages
    thread_id = str(uuid4())
    thread = Thread(
        thread_id=thread_id,
        user_id=user.user_id,
        agent_id=agent.agent_id,
        name="SQL Generation",
        messages=[],
    )
    await sqlite_storage.upsert_thread(user.user_id, thread)

    agent_messages = [
        ThreadAgentMessage(
            role="agent",
            content=[ThreadTextContent(text="Analyzing the schema...")],
        ),
        ThreadAgentMessage(
            role="agent",
            content=[ThreadTextContent(text="Generated SQL successfully")],
        ),
    ]

    # Create actual SQL content and save it as a file
    sql_content = SQLGenerationContent(
        status=SQLGenerationStatus.SUCCESS, sql_query="SELECT * FROM test_table"
    )

    # Write file to temp filesystem and register in database
    file_id = str(uuid4())
    file_content = sql_content.model_dump_json().encode("utf-8")
    file_hash = hashlib.sha256(file_content).hexdigest()

    file_path = tmp_path / file_id
    file_path.write_bytes(file_content)

    # Register file in database
    await sqlite_storage.put_file_owner(
        file_id=file_id,
        file_path=file_path.as_uri(),
        file_ref="output.json",
        file_hash=file_hash,
        file_size_raw=len(file_content),
        mime_type="application/json",
        user_id=user.user_id,
        embedded=False,
        embedding_status=None,
        owner=thread,
        file_path_expiration=None,
    )

    # Create SQL generation details
    sql_details = SQLGenerationDetails(
        agent_messages=agent_messages,
        intent="Get all records from test table",
        semantic_data_model_name="test_sdm",
    )

    # Act
    result = await _create_internal_tool_response_from_sql_thread(
        thread=thread,
        storage=sqlite_storage,
        user_id=user.user_id,
        details=sql_details,
        file_manager=FileManagerService.get_instance(storage=sqlite_storage, manager_type="local"),
    )

    # Assert
    assert result.result is not None
    assert result.error is None

    # Verify execution_metadata structure
    assert "sql_generation_details" in result.execution_metadata
    details_dict = result.execution_metadata["sql_generation_details"]
    assert details_dict["intent"] == "Get all records from test table"
    assert details_dict["semantic_data_model_name"] == "test_sdm"
    assert "agent_messages" in details_dict
    assert isinstance(details_dict["agent_messages"], list)
    assert len(details_dict["agent_messages"]) == 2
    assert details_dict["agent_messages"][0]["content"][0]["text"] == "Analyzing the schema..."
    assert details_dict["agent_messages"][1]["content"][0]["text"] == "Generated SQL successfully"


@pytest.mark.asyncio
async def test_collect_thread_files_for_sdm():
    storage = AsyncMock()
    kernel = MagicMock()
    kernel.thread.thread_id = "t1"
    kernel.thread.agent_id = "a1"
    kernel.user.user_id = "u1"

    now = datetime.now(UTC)
    file_a = UploadedFile(
        file_id="1",
        file_path=None,
        file_ref="a.csv",
        file_hash="",
        file_size_raw=0,
        mime_type="text/csv",
        created_at=now,
    )
    file_b = UploadedFile(
        file_id="2",
        file_path=None,
        file_ref="b.csv",
        file_hash="",
        file_size_raw=0,
        mime_type="text/csv",
        created_at=now,
    )
    storage.get_thread_files.return_value = [file_a, file_b]

    references = References(
        data_connection_ids=set(),
        data_frame_names=set(),
        file_references={_FileReference(thread_id="t1", file_ref="b.csv", sheet_name=None)},
        data_connection_id_to_logical_table_names={},
        file_reference_to_logical_table_names={},
        logical_table_name_to_connection_info={},
        errors=[],
        _structured_errors=[],
        tables_with_unresolved_file_references=set(),
        semantic_data_model_with_errors=None,
    )

    collector = MagicMock(
        resolve_file_references_for_semantic_data_model=AsyncMock(return_value=({}, references))
    )
    sdm = {"name": "sdm", "tables": []}

    selected = await _collect_sdm_files(
        storage=storage,
        kernel=kernel,
        semantic_data_model=sdm,  # type: ignore[arg-type]
        collector=collector,
    )

    assert selected == [file_b]


@pytest.mark.asyncio
async def test_upload_sdm_files(tmp_path, sqlite_storage):
    kernel = MagicMock()

    # Create a user
    user, _created = await sqlite_storage.get_or_create_user("user")
    user_id = user.user_id
    kernel.user.user_id = user_id

    # Create an agent
    agent = Agent(
        user_id=user_id,
        agent_id=str(uuid4()),
        name="Test Agent",
        description="Test Description",
        runbook_structured=Runbook(
            raw_text="# Objective\nYou are a helpful assistant.", content=[]
        ),
        version="1.0.0",
        platform_configs=[],
        agent_architecture=AgentArchitecture(
            name="agent_platform.architectures.default", version="1.0.0"
        ),
    )
    await sqlite_storage.upsert_agent(user_id, agent)

    # Create a "user" thread
    source_thread = Thread(
        user_id=user_id,
        agent_id=agent.agent_id,
        name="Source Thread",
        thread_id=str(uuid4()),
    )
    # Create a "sql agent" thread (We're avoiding creating the pre-installed agent)
    sql_thread = Thread(
        user_id=user_id,
        agent_id=agent.agent_id,
        name="SQL Thread",
        thread_id=str(uuid4()),
    )
    await sqlite_storage.upsert_thread(user_id, source_thread)
    await sqlite_storage.upsert_thread(user_id, sql_thread)

    FileManagerService.reset()
    file_manager = FileManagerService.get_instance(storage=sqlite_storage, manager_type="local")

    # Upload a file to the user thread.
    temp_file = SpooledTemporaryFile()
    temp_file.write(b"col\n1\n")
    temp_file.seek(0)
    upload = UploadFile(
        filename="a.csv",
        file=cast(BinaryIO, temp_file),
        headers=Headers({"content-type": "text/csv"}),
    )

    uploaded_to_source = await file_manager.upload(
        files=[UploadFilePayload(file=upload)],
        owner=source_thread,
        user_id=user_id,
    )
    assert len(uploaded_to_source) == 1
    source_uploaded = uploaded_to_source[0]

    # Fake that we have identified this file as being referenced by the SDM.
    source_files = await sqlite_storage.get_thread_files(source_thread.thread_id, user_id)
    assert any(f.file_id == source_uploaded.file_id and f.file_ref == "a.csv" for f in source_files)

    # Upload the file to the sql thread.
    copied = await _upload_sdm_files(
        kernel=kernel,
        sql_thread=sql_thread,
        file_manager=file_manager,
        files_to_upload=[source_uploaded],
    )

    # Verify it got to the correct place.
    sql_files = await sqlite_storage.get_thread_files(sql_thread.thread_id, user_id)

    assert len(copied) == 1
    assert copied[0].file_ref == source_uploaded.file_ref
    assert copied[0].mime_type == source_uploaded.mime_type
    assert any(f.file_ref == "a.csv" and f.file_id != source_uploaded.file_id for f in sql_files)
