"""Unit tests for semantic data model generator."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_platform.core.payloads.data_connection import (
    ColumnInfo as DataConnectionColumnInfo,
)
from agent_platform.core.payloads.data_connection import (
    DataConnectionsInspectRequest,
    DataConnectionsInspectResponse,
)
from agent_platform.core.payloads.data_connection import (
    TableInfo as DataConnectionTableInfo,
)
from agent_platform.core.payloads.semantic_data_model_payloads import (
    ColumnInfo,
    DataConnectionInfo,
    FileInfo,
    TableInfo,
)
from agent_platform.server.kernel.semantic_data_model_generator import (
    SemanticDataModelGenerator,
)


@pytest.fixture
def mock_storage(monkeypatch):
    """Create a mock storage with necessary methods."""
    storage = AsyncMock()
    # Mock data connection retrieval
    mock_connection = MagicMock()
    mock_connection.id = "conn_123"
    mock_connection.name = "test_connection"
    mock_connection.engine = "postgres"
    storage.get_data_connection.return_value = mock_connection

    # Mock DataConnectionInspector.create_ibis_connection to avoid actual connection
    mock_ibis_connection = AsyncMock()

    async def mock_create_ibis_connection(*args, **kwargs):
        return mock_ibis_connection

    from agent_platform.server.kernel import data_connection_inspector

    monkeypatch.setattr(
        data_connection_inspector.DataConnectionInspector,
        "create_ibis_connection",
        mock_create_ibis_connection,
    )

    # Mock ForeignKeyInspector methods to return empty constraints
    async def mock_get_foreign_keys(*args, **kwargs):
        return {}

    async def mock_get_primary_keys(*args, **kwargs):
        return {}

    from agent_platform.server.dialect.postgres import foreign_key_inspector

    monkeypatch.setattr(
        foreign_key_inspector.PostgresForeignKeyInspector,
        "get_foreign_keys",
        mock_get_foreign_keys,
    )
    monkeypatch.setattr(
        foreign_key_inspector.PostgresForeignKeyInspector,
        "get_primary_keys",
        mock_get_primary_keys,
    )

    return storage


@pytest.mark.asyncio
async def test_generate_semantic_data_model_with_data_connection(data_regression, mock_storage):
    """Test generating a semantic data model from data connection info."""
    generator = SemanticDataModelGenerator(storage=mock_storage)

    # Create sample data
    column_info = ColumnInfo(
        name="user_id",
        data_type="INTEGER",
        sample_values=[1, 2, 3],
        description="User identifier",
        synonyms=["id", "user_identifier"],
    )

    table_info = TableInfo(
        name="users",
        database="test_db",
        schema="public",
        description="User table",
        columns=[column_info],
    )

    data_connection_info = DataConnectionInfo(
        data_connection_id="conn_123",
        tables_info=[table_info],
    )

    # Generate semantic model (without metadata for basic structure test)
    result = await generator.generate_semantic_data_model(
        name="test_model",
        description="Test semantic model",
        data_connections_info=[data_connection_info],
        files_info=[],
        include_metadata=False,
    )

    data_regression.check(result)


@pytest.mark.asyncio
async def test_generate_semantic_data_model_with_file(data_regression):
    """Test generating a semantic data model from file info."""
    generator = SemanticDataModelGenerator()

    # Create sample data
    column_info = ColumnInfo(
        name="product_name",
        data_type="TEXT",
        sample_values=["Product A", "Product B"],
        description="Product name",
        synonyms=["name", "product"],
    )

    table_info = TableInfo(
        name="products",
        database=None,
        schema=None,
        description="Product table",
        columns=[column_info],
    )

    file_info = FileInfo(
        thread_id="thread_123",
        file_ref="file_456",
        sheet_name="Sheet1",
        tables_info=[table_info],
    )

    # Generate semantic model (without metadata for basic structure test)
    result = await generator.generate_semantic_data_model(
        name="file_model",
        description="File-based semantic model",
        data_connections_info=[],
        files_info=[file_info],
        include_metadata=False,
    )

    data_regression.check(result)


@pytest.mark.asyncio
async def test_generate_semantic_data_model_with_numeric_columns(data_regression, mock_storage):
    """Test generating a semantic data model with numeric columns (facts)."""
    generator = SemanticDataModelGenerator(storage=mock_storage)

    # Create sample data with numeric column
    numeric_column = ColumnInfo(
        name="price",
        data_type="DECIMAL",
        sample_values=[10.99, 20.50],
        description="Product price",
        synonyms=["cost", "amount"],
    )

    table_info = TableInfo(
        name="products",
        database="test_db",
        schema="public",
        description="Product table",
        columns=[numeric_column],
    )

    data_connection_info = DataConnectionInfo(
        data_connection_id="conn_123",
        tables_info=[table_info],
    )

    # Generate semantic model (without metadata for basic structure test)
    result = await generator.generate_semantic_data_model(
        name="numeric_model",
        description="Model with numeric columns",
        data_connections_info=[data_connection_info],
        files_info=[],
        include_metadata=False,
    )

    data_regression.check(result)


@pytest.mark.asyncio
async def test_generate_semantic_data_model_with_time_columns(data_regression, mock_storage):
    """Test generating a semantic data model with time columns."""
    generator = SemanticDataModelGenerator(storage=mock_storage)

    # Create sample data with time column
    time_column = ColumnInfo(
        name="created_at",
        data_type="TIMESTAMP",
        sample_values=["2023-01-01 10:00:00", "2023-01-02 11:00:00"],
        description="Creation timestamp",
        synonyms=["timestamp", "date_created"],
    )

    table_info = TableInfo(
        name="events",
        database="test_db",
        schema="public",
        description="Event table",
        columns=[time_column],
    )

    data_connection_info = DataConnectionInfo(
        data_connection_id="conn_123",
        tables_info=[table_info],
    )

    # Generate semantic model (without metadata for basic structure test)
    result = await generator.generate_semantic_data_model(
        name="time_model",
        description="Model with time columns",
        data_connections_info=[data_connection_info],
        files_info=[],
        include_metadata=False,
    )

    data_regression.check(result)


@pytest.mark.asyncio
async def test_generate_semantic_data_model_with_metadata(mock_storage):
    """Test that semantic data model generator creates metadata."""
    generator = SemanticDataModelGenerator(storage=mock_storage)

    # Create sample data (using data_connection types for inspection API)
    column_info = DataConnectionColumnInfo(
        name="user_id",
        data_type="INTEGER",
        sample_values=[1, 2, 3],
        primary_key=None,
        unique=None,
        description="User identifier",
        synonyms=None,
    )

    table_info = DataConnectionTableInfo(
        name="users",
        database="test_db",
        schema="public",
        description="User table",
        columns=[column_info],
    )

    # Create inspection request and response
    inspect_request = DataConnectionsInspectRequest(tables_to_inspect=None)
    inspect_response = DataConnectionsInspectResponse(
        tables=[table_info],
        inspected_at="2024-01-15T10:00:00Z",
    )

    # Create TableInfo list for generator input (using semantic_data_model_payloads types)
    generator_column_info = ColumnInfo(
        name="user_id",
        data_type="INTEGER",
        sample_values=[1, 2, 3],
        description="User identifier",
    )

    generator_table_info = TableInfo(
        name="users",
        database="test_db",
        schema="public",
        description="User table",
        columns=[generator_column_info],
    )

    data_connection_info = DataConnectionInfo(
        data_connection_id="conn_123",
        tables_info=[generator_table_info],
        inspect_request=inspect_request,
        inspect_response=inspect_response,
    )

    # Generate semantic model with metadata
    result = await generator.generate_semantic_data_model(
        name="test_model",
        description="Test semantic model",
        data_connections_info=[data_connection_info],
        files_info=[],
        include_metadata=True,
    )

    # Verify metadata was created
    assert "metadata" in result
    assert result["metadata"] is not None
    assert "input_data_connection_snapshots" in result["metadata"]

    snapshots = result["metadata"]["input_data_connection_snapshots"]
    assert isinstance(snapshots, list)
    assert len(snapshots) == 1

    snapshot = snapshots[0]
    assert snapshot.get("kind") == "data_connection"
    assert "inspected_at" in snapshot
    assert snapshot.get("inspected_at") == "2024-01-15T10:00:00Z"
    assert "inspection_result" in snapshot
    assert "inspection_request_info" in snapshot

    # Verify provenance metadata
    request_info = snapshot.get("inspection_request_info")
    assert request_info is not None
    assert request_info.get("data_connection_id") == "conn_123"
    assert request_info.get("data_connection_name") == "test_connection"
    assert request_info.get("data_connection_inspect_request") is not None

    # Verify we can extract the DataConnectionsInspectResponse
    inspection_result = snapshot.get("inspection_result")
    assert inspection_result is not None

    tables = inspection_result.tables
    assert tables is not None
    assert len(tables) == 1

    # Verify table info structure (same as inspection API returns)
    table = tables[0]
    assert table.name == "users"
    assert table.database == "test_db"
    assert table.schema == "public"

    columns = table.columns
    assert columns is not None
    assert len(columns) == 1
    assert columns[0].name == "user_id"
    assert columns[0].data_type == "INTEGER"
    assert columns[0].sample_values == [1, 2, 3]

    # Test without metadata (backward compatibility)
    data_connection_info_no_inspect = DataConnectionInfo(
        data_connection_id="conn_123",
        tables_info=[generator_table_info],
    )

    result_no_metadata = await generator.generate_semantic_data_model(
        name="test_model_no_metadata",
        description="Test semantic model without metadata",
        data_connections_info=[data_connection_info_no_inspect],
        files_info=[],
        include_metadata=False,
    )

    # Verify no metadata was created
    assert "metadata" not in result_no_metadata or result_no_metadata.get("metadata") is None


@pytest.mark.asyncio
async def test_generate_semantic_data_model_with_file_metadata():
    """Test that semantic data model generator creates metadata for files."""
    generator = SemanticDataModelGenerator()

    # Create sample file data with multiple sheets (using data_connection types for inspection API)
    column_info_1 = DataConnectionColumnInfo(
        name="product_name",
        data_type="TEXT",
        sample_values=["Product A", "Product B"],
        primary_key=None,
        unique=None,
        description=None,
        synonyms=None,
    )

    table_info_1 = DataConnectionTableInfo(
        name="Sheet1",
        database="test_file.xlsx",  # Filename used as database for grouping
        schema=None,
        description=None,
        columns=[column_info_1],
    )

    column_info_2 = DataConnectionColumnInfo(
        name="category",
        data_type="TEXT",
        sample_values=["Electronics", "Books"],
        primary_key=None,
        unique=None,
        description=None,
        synonyms=None,
    )

    table_info_2 = DataConnectionTableInfo(
        name="Sheet2",
        database="test_file.xlsx",  # Filename used as database for grouping
        schema=None,
        description=None,
        columns=[column_info_2],
    )

    # Create inspection response for file
    inspect_response = DataConnectionsInspectResponse(
        tables=[table_info_1, table_info_2],
        inspected_at="2024-01-15T10:00:00Z",
    )

    # Create TableInfo list for generator input (using semantic_data_model_payloads types)
    generator_column_info_1 = ColumnInfo(
        name="product_name",
        data_type="TEXT",
        sample_values=["Product A", "Product B"],
    )

    generator_table_info_1 = TableInfo(
        name="Sheet1",
        database="test_file.xlsx",
        schema=None,
        columns=[generator_column_info_1],
    )

    generator_column_info_2 = ColumnInfo(
        name="category",
        data_type="TEXT",
        sample_values=["Electronics", "Books"],
    )

    generator_table_info_2 = TableInfo(
        name="Sheet2",
        database="test_file.xlsx",
        schema=None,
        columns=[generator_column_info_2],
    )

    file_info = FileInfo(
        thread_id="thread_123",
        file_ref="file_456",
        sheet_name=None,
        tables_info=[generator_table_info_1, generator_table_info_2],
        inspect_response=inspect_response,
    )

    # Generate semantic model with metadata
    result = await generator.generate_semantic_data_model(
        name="file_model",
        description="File-based semantic model",
        data_connections_info=[],
        files_info=[file_info],
        include_metadata=True,
    )

    # Verify metadata was created for file
    assert "metadata" in result
    assert result["metadata"] is not None
    assert "input_data_connection_snapshots" in result["metadata"]

    snapshots = result["metadata"]["input_data_connection_snapshots"]
    assert isinstance(snapshots, list)
    assert len(snapshots) == 1

    snapshot = snapshots[0]
    assert snapshot.get("kind") == "file"
    assert "inspected_at" in snapshot
    assert snapshot.get("inspected_at") == "2024-01-15T10:00:00Z"
    assert "inspection_result" in snapshot
    assert "inspection_request_info" in snapshot

    # Verify provenance info
    request_info = snapshot.get("inspection_request_info")
    assert request_info is not None
    file_reference = request_info.get("file_reference")
    assert file_reference is not None
    assert file_reference.get("thread_id") == "thread_123"
    assert file_reference.get("file_ref") == "file_456"

    # Verify we can extract the DataConnectionsInspectResponse
    inspection_result = snapshot.get("inspection_result")
    assert inspection_result is not None

    tables = inspection_result.tables
    assert tables is not None
    assert len(tables) == 2

    # Verify table structure (same as inspection API returns)
    assert tables[0].name == "Sheet1"
    assert tables[0].database == "test_file.xlsx"  # Filename for grouping
    assert tables[0].schema is None
    assert tables[1].name == "Sheet2"
    assert tables[1].database == "test_file.xlsx"  # Same file
    assert tables[1].schema is None


def test_distinct_sample_values():
    """Test _get_sample_values normalizes and deduplicates sample values correctly."""
    generator = SemanticDataModelGenerator()

    # Test with mixed types including duplicates
    sample_values = [
        "apple",
        "banana",
        "apple",  # Duplicate string
        123,
        456,
        123,  # Duplicate int
        12.5,
        12.5,  # Duplicate float
        True,
        False,
        True,  # Duplicate bool
        None,
        None,  # Duplicate None
        1,  # Should be kept separate from True despite Python's bool/int equality
    ]

    expected = [
        "apple",
        "banana",
        123,
        456,
        12.5,
        True,
        False,
        None,
        1,
    ]

    result = generator._get_sample_values(sample_values)

    # Should deduplicate while preserving first-seen order
    assert result == expected
