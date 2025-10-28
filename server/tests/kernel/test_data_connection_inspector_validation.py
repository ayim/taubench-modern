"""Unit tests for DataConnectionInspector validation methods."""

from unittest.mock import Mock

import pytest


@pytest.mark.asyncio
async def test_validate_tables_exist_success():
    """Test validate_tables_exist when all tables exist."""
    from agent_platform.core.data_connections.data_connections import DataConnection
    from agent_platform.core.payloads.data_connection import (
        DataConnectionsInspectRequest,
        TableToInspect,
    )
    from agent_platform.server.kernel.data_connection_inspector import (
        DataConnectionInspector,
    )

    data_connection = Mock(spec=DataConnection)
    request = DataConnectionsInspectRequest(
        tables_to_inspect=[
            TableToInspect(name="table1", database=None, schema=None),
            TableToInspect(name="table2", database=None, schema=None),
        ],
        inspect_columns=False,
        n_sample_rows=0,
    )

    inspector = DataConnectionInspector(data_connection, request)

    # Mock the connection and table objects
    mock_connection = Mock()
    mock_table1 = Mock()
    mock_table1.schema.return_value = Mock()  # Successful schema access
    mock_table2 = Mock()
    mock_table2.schema.return_value = Mock()

    def mock_get_table(name):
        if name == "table1":
            return mock_table1
        elif name == "table2":
            return mock_table2
        raise Exception(f"Table {name} not found")

    mock_connection.table = mock_get_table
    inspector._connection = mock_connection

    errors = await inspector.validate_tables_exist()
    assert errors == {}


@pytest.mark.asyncio
async def test_validate_tables_exist_with_missing_table():
    """Test validate_tables_exist when a table is missing."""
    from agent_platform.core.data_connections.data_connections import DataConnection
    from agent_platform.core.payloads.data_connection import (
        DataConnectionsInspectRequest,
        TableToInspect,
    )
    from agent_platform.server.kernel.data_connection_inspector import (
        DataConnectionInspector,
        TableNotFoundError,
    )

    data_connection = Mock(spec=DataConnection)
    request = DataConnectionsInspectRequest(
        tables_to_inspect=[
            TableToInspect(name="existing_table", database=None, schema=None),
            TableToInspect(name="missing_table", database=None, schema=None),
        ],
        inspect_columns=False,
        n_sample_rows=0,
    )

    inspector = DataConnectionInspector(data_connection, request)

    # Mock _get_table to raise TableNotFoundError for missing_table
    async def mock_get_table(table_spec):
        if table_spec.name == "missing_table":
            raise TableNotFoundError("missing_table", "Table does not exist in database")
        mock_table = Mock()
        mock_table.schema.return_value = Mock()
        return mock_table

    inspector._get_table = mock_get_table

    errors = await inspector.validate_tables_exist()
    assert len(errors) == 1
    assert "missing_table" in errors
    assert "not found" in errors["missing_table"].lower()


@pytest.mark.asyncio
async def test_validate_tables_exist_with_access_error():
    """Test validate_tables_exist when table access fails."""
    from agent_platform.core.data_connections.data_connections import DataConnection
    from agent_platform.core.payloads.data_connection import (
        DataConnectionsInspectRequest,
        TableToInspect,
    )
    from agent_platform.server.kernel.data_connection_inspector import (
        DataConnectionInspector,
    )

    data_connection = Mock(spec=DataConnection)
    request = DataConnectionsInspectRequest(
        tables_to_inspect=[
            TableToInspect(name="error_table", database=None, schema=None),
        ],
        inspect_columns=False,
        n_sample_rows=0,
    )

    inspector = DataConnectionInspector(data_connection, request)

    # Mock _get_table to return a table that fails on schema access
    async def mock_get_table(table_spec):
        mock_table = Mock()
        mock_table.schema.side_effect = Exception("Permission denied")
        return mock_table

    inspector._get_table = mock_get_table

    errors = await inspector.validate_tables_exist()
    assert len(errors) == 1
    assert "error_table" in errors
    assert "error accessing table" in errors["error_table"].lower()


@pytest.mark.asyncio
async def test_validate_tables_exist_no_tables_specified():
    """Test validate_tables_exist raises error when no tables specified."""
    from agent_platform.core.data_connections.data_connections import DataConnection
    from agent_platform.core.payloads.data_connection import (
        DataConnectionsInspectRequest,
    )
    from agent_platform.server.kernel.data_connection_inspector import (
        DataConnectionInspector,
    )

    data_connection = Mock(spec=DataConnection)
    request = DataConnectionsInspectRequest(
        tables_to_inspect=None,
        inspect_columns=False,
        n_sample_rows=0,
    )

    inspector = DataConnectionInspector(data_connection, request)

    with pytest.raises(ValueError, match="No tables specified"):
        await inspector.validate_tables_exist()


@pytest.mark.asyncio
async def test_validate_column_expressions_success():
    """Test validate_column_expressions when all columns are valid."""
    from agent_platform.core.data_connections.data_connections import DataConnection
    from agent_platform.core.payloads.data_connection import (
        DataConnectionsInspectRequest,
        TableToInspect,
    )
    from agent_platform.server.kernel.data_connection_inspector import (
        DataConnectionInspector,
    )

    data_connection = Mock(spec=DataConnection)
    request = DataConnectionsInspectRequest(
        tables_to_inspect=[
            TableToInspect(
                name="table1",
                database=None,
                schema=None,
                columns_to_inspect=["col1", "col2"],
            ),
        ],
        inspect_columns=True,
        n_sample_rows=0,
    )

    inspector = DataConnectionInspector(data_connection, request)

    # Mock table with valid columns
    mock_table = Mock()
    mock_table.columns = ["col1", "col2", "col3"]
    mock_table.schema.return_value = Mock()

    async def mock_get_table(table_spec):
        return mock_table

    inspector._get_table = mock_get_table

    errors = await inspector.validate_column_expressions()
    assert errors == {}


@pytest.mark.asyncio
async def test_validate_column_expressions_with_invalid_expression():
    """Test validate_column_expressions when a column expression is invalid."""
    from agent_platform.core.data_connections.data_connections import DataConnection
    from agent_platform.core.payloads.data_connection import (
        DataConnectionsInspectRequest,
        TableToInspect,
    )
    from agent_platform.server.kernel.data_connection_inspector import (
        DataConnectionInspector,
    )

    data_connection = Mock(spec=DataConnection)
    request = DataConnectionsInspectRequest(
        tables_to_inspect=[
            TableToInspect(
                name="table1",
                database=None,
                schema=None,
                columns_to_inspect=["col1", "invalid_expr"],
            ),
        ],
        inspect_columns=True,
        n_sample_rows=0,
    )

    inspector = DataConnectionInspector(data_connection, request)

    # Mock table with only col1 in columns
    mock_table = Mock()
    mock_table.columns = ["col1"]
    mock_table.schema.return_value = Mock()

    # Mock validate_column_expression to fail for invalid_expr
    async def mock_validate_column_expression(table, column_expression):
        if column_expression == "invalid_expr":
            return "Invalid column expression: Column not found"
        return None

    async def mock_get_table(table_spec):
        return mock_table

    inspector._get_table = mock_get_table
    inspector._validate_column_expression = mock_validate_column_expression

    errors = await inspector.validate_column_expressions()
    assert len(errors) == 1
    assert "table1" in errors
    assert "invalid_expr" in errors["table1"]
    assert "invalid column expression" in errors["table1"]["invalid_expr"].lower()


@pytest.mark.asyncio
async def test_validate_column_expressions_with_table_error():
    """Test validate_column_expressions when table validation fails."""
    from agent_platform.core.data_connections.data_connections import DataConnection
    from agent_platform.core.payloads.data_connection import (
        DataConnectionsInspectRequest,
        TableToInspect,
    )
    from agent_platform.server.kernel.data_connection_inspector import (
        TABLE_VALIDATION_ERROR_KEY,
        DataConnectionInspector,
        TableNotFoundError,
    )

    data_connection = Mock(spec=DataConnection)
    request = DataConnectionsInspectRequest(
        tables_to_inspect=[
            TableToInspect(
                name="missing_table",
                database=None,
                schema=None,
                columns_to_inspect=["col1"],
            ),
        ],
        inspect_columns=True,
        n_sample_rows=0,
    )

    inspector = DataConnectionInspector(data_connection, request)

    # Mock _get_table to raise TableNotFoundError
    async def mock_get_table(table_spec):
        raise TableNotFoundError("missing_table", "Table not found in database")

    inspector._get_table = mock_get_table

    errors = await inspector.validate_column_expressions()
    assert len(errors) == 1
    assert "missing_table" in errors
    assert TABLE_VALIDATION_ERROR_KEY in errors["missing_table"]
    assert "not found" in errors["missing_table"][TABLE_VALIDATION_ERROR_KEY].lower()


@pytest.mark.asyncio
async def test_validate_column_expressions_missing_columns_to_inspect():
    """Test validate_column_expressions raises error when columns_to_inspect is None."""
    from agent_platform.core.data_connections.data_connections import DataConnection
    from agent_platform.core.payloads.data_connection import (
        DataConnectionsInspectRequest,
        TableToInspect,
    )
    from agent_platform.server.kernel.data_connection_inspector import (
        DataConnectionInspector,
    )

    data_connection = Mock(spec=DataConnection)
    request = DataConnectionsInspectRequest(
        tables_to_inspect=[
            TableToInspect(
                name="table1",
                database=None,
                schema=None,
                columns_to_inspect=None,  # Missing columns_to_inspect
            ),
        ],
        inspect_columns=True,
        n_sample_rows=0,
    )

    inspector = DataConnectionInspector(data_connection, request)

    with pytest.raises(ValueError, match="has no columns_to_inspect specified"):
        await inspector.validate_column_expressions()


@pytest.mark.asyncio
async def test_validate_column_expressions_no_tables_specified():
    """Test validate_column_expressions raises error when no tables specified."""
    from agent_platform.core.data_connections.data_connections import DataConnection
    from agent_platform.core.payloads.data_connection import (
        DataConnectionsInspectRequest,
    )
    from agent_platform.server.kernel.data_connection_inspector import (
        DataConnectionInspector,
    )

    data_connection = Mock(spec=DataConnection)
    request = DataConnectionsInspectRequest(
        tables_to_inspect=None,
        inspect_columns=True,
        n_sample_rows=0,
    )

    inspector = DataConnectionInspector(data_connection, request)

    with pytest.raises(ValueError, match="No tables specified"):
        await inspector.validate_column_expressions()


@pytest.mark.asyncio
async def test_validate_column_expression_method():
    """Test _validate_column_expression method directly."""
    from agent_platform.core.data_connections.data_connections import DataConnection
    from agent_platform.core.payloads.data_connection import (
        DataConnectionsInspectRequest,
    )
    from agent_platform.server.kernel.data_connection_inspector import (
        DataConnectionInspector,
    )

    data_connection = Mock(spec=DataConnection)
    request = DataConnectionsInspectRequest(
        tables_to_inspect=[],
        inspect_columns=False,
        n_sample_rows=0,
    )

    inspector = DataConnectionInspector(data_connection, request)

    # Mock a table that will succeed for valid expressions
    mock_table = Mock()
    mock_select_result = Mock()
    mock_limit_result = Mock()
    mock_limit_result.execute.return_value = []
    mock_select_result.limit.return_value = mock_limit_result
    mock_table.select.return_value = mock_select_result

    error = await inspector._validate_column_expression(mock_table, "valid_column")
    assert error is None

    # Mock a table that will fail for invalid expressions
    mock_table_error = Mock()
    mock_select_error = Mock()
    mock_limit_error = Mock()
    mock_limit_error.execute.side_effect = Exception("Column not found")
    mock_select_error.limit.return_value = mock_limit_error
    mock_table_error.select.return_value = mock_select_error

    error = await inspector._validate_column_expression(mock_table_error, "invalid_column")
    assert error is not None
    assert "invalid column expression" in error.lower()
