"""Tests for async ibis proxy classes."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_platform.server.kernel.ibis_async_proxy import (
    AsyncIbisColumn,
    AsyncIbisConnection,
    AsyncIbisTable,
)


@pytest.fixture
def mock_ibis_connection():
    """Create a mock ibis connection."""
    conn = MagicMock()
    conn.table = MagicMock()
    conn.list_tables = MagicMock(return_value=["table1", "table2"])
    conn.sql = MagicMock()
    conn.create_table = MagicMock()
    conn.current_schema = "public"
    conn.current_database = "testdb"
    return conn


@pytest.fixture
def mock_ibis_table():
    """Create a mock ibis table."""
    table = MagicMock()
    table.columns = ["col1", "col2", "col3"]
    table.schema = MagicMock()
    table.select = MagicMock(return_value=MagicMock())
    table.limit = MagicMock(return_value=MagicMock())
    table.filter = MagicMock(return_value=MagicMock())
    table.__getitem__ = MagicMock()
    return table


class TestAsyncIbisConnection:
    """Tests for AsyncIbisConnection class."""

    @pytest.mark.asyncio
    async def test_table_returns_async_table(self, mock_ibis_connection):
        """Test that table() returns an AsyncIbisTable."""
        mock_table = MagicMock()
        mock_ibis_connection.table.return_value = mock_table

        async_conn = AsyncIbisConnection(mock_ibis_connection, engine="postgres")

        result = await async_conn.table("test_table")

        assert isinstance(result, AsyncIbisTable)
        assert result._engine == "postgres"
        mock_ibis_connection.table.assert_called_once_with("test_table")

    @pytest.mark.asyncio
    async def test_list_tables_uses_thread(self, mock_ibis_connection):
        """Test that list_tables() uses asyncio.to_thread."""
        async_conn = AsyncIbisConnection(mock_ibis_connection, engine="postgres")

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = ["table1", "table2"]
            result = await async_conn.list_tables()

            assert result == ["table1", "table2"]
            mock_to_thread.assert_called_once_with(mock_ibis_connection.list_tables)

    @pytest.mark.asyncio
    async def test_sql_returns_async_table(self, mock_ibis_connection):
        """Test that sql() returns an AsyncIbisTable."""
        mock_expr = MagicMock()
        mock_ibis_connection.sql.return_value = mock_expr

        async_conn = AsyncIbisConnection(mock_ibis_connection, engine="postgres")

        result = await async_conn.sql("SELECT * FROM test")

        assert isinstance(result, AsyncIbisTable)
        assert result._engine == "postgres"

    @pytest.mark.asyncio
    async def test_create_table_uses_thread(self, mock_ibis_connection):
        """Test that create_table() uses asyncio.to_thread."""
        async_conn = AsyncIbisConnection(mock_ibis_connection, engine="postgres")
        mock_obj = MagicMock()

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            await async_conn.create_table("new_table", mock_obj)

            mock_to_thread.assert_called_once_with(
                mock_ibis_connection.create_table, "new_table", mock_obj
            )

    @pytest.mark.asyncio
    async def test_get_current_schema(self, mock_ibis_connection):
        """Test that get_current_schema() uses asyncio.to_thread."""
        async_conn = AsyncIbisConnection(mock_ibis_connection, engine="postgres")

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = "public"
            result = await async_conn.get_current_schema()

            assert result == "public"
            assert mock_to_thread.called

    @pytest.mark.asyncio
    async def test_get_current_database(self, mock_ibis_connection):
        """Test that get_current_database() uses asyncio.to_thread."""
        async_conn = AsyncIbisConnection(mock_ibis_connection, engine="postgres")

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = "testdb"
            result = await async_conn.get_current_database()

            assert result == "testdb"
            assert mock_to_thread.called

    def test_engine_stored(self, mock_ibis_connection):
        """Test that engine name is stored."""
        async_conn = AsyncIbisConnection(mock_ibis_connection, engine="snowflake")
        assert async_conn._engine == "snowflake"


class TestAsyncIbisTable:
    """Tests for AsyncIbisTable class."""

    @pytest.mark.asyncio
    async def test_schema_uses_thread(self, mock_ibis_table):
        """Test that schema() uses asyncio.to_thread."""
        async_table = AsyncIbisTable(mock_ibis_table, engine="postgres")
        mock_schema = MagicMock()

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = mock_schema
            result = await async_table.schema()

            assert result == mock_schema
            mock_to_thread.assert_called_once_with(mock_ibis_table.schema)

    @pytest.mark.asyncio
    async def test_to_pyarrow_uses_backend_handler(self, mock_ibis_table):
        """Test that to_pyarrow() uses execute_query_with_backend_handler."""
        async_table = AsyncIbisTable(mock_ibis_table, engine="postgres")
        mock_arrow_table = MagicMock()

        with patch(
            "agent_platform.server.semantic_data_models.handlers.execute_query_with_backend_handler",
            new_callable=AsyncMock,
        ) as mock_handler:
            mock_handler.return_value = mock_arrow_table
            result = await async_table.to_pyarrow()

            assert result == mock_arrow_table
            mock_handler.assert_called_once_with(mock_ibis_table, engine="postgres")

    @pytest.mark.asyncio
    async def test_execute_uses_thread(self, mock_ibis_table):
        """Test that execute() uses asyncio.to_thread."""
        async_table = AsyncIbisTable(mock_ibis_table, engine="postgres")

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            await async_table.execute()
            mock_to_thread.assert_called_once_with(mock_ibis_table.execute)

    def test_select_returns_async_table(self, mock_ibis_table):
        """Test that select() returns an AsyncIbisTable (lazy operation)."""
        async_table = AsyncIbisTable(mock_ibis_table, engine="postgres")
        mock_expr = MagicMock()
        mock_ibis_table.select.return_value = mock_expr

        result = async_table.select("col1", "col2")

        assert isinstance(result, AsyncIbisTable)
        assert result._engine == "postgres"
        mock_ibis_table.select.assert_called_once_with("col1", "col2")

    def test_limit_returns_async_table(self, mock_ibis_table):
        """Test that limit() returns an AsyncIbisTable (lazy operation)."""
        async_table = AsyncIbisTable(mock_ibis_table, engine="postgres")
        mock_expr = MagicMock()
        mock_ibis_table.limit.return_value = mock_expr

        result = async_table.limit(10)

        assert isinstance(result, AsyncIbisTable)
        assert result._engine == "postgres"
        mock_ibis_table.limit.assert_called_once_with(10)

    def test_filter_returns_async_table(self, mock_ibis_table):
        """Test that filter() returns an AsyncIbisTable (lazy operation)."""
        async_table = AsyncIbisTable(mock_ibis_table, engine="postgres")
        mock_expr = MagicMock()
        mock_ibis_table.filter.return_value = mock_expr

        result = async_table.filter("col1 > 10")

        assert isinstance(result, AsyncIbisTable)
        assert result._engine == "postgres"

    def test_columns_property_direct_access(self, mock_ibis_table):
        """Test that columns property is directly accessible (cached, no I/O)."""
        async_table = AsyncIbisTable(mock_ibis_table, engine="postgres")

        result = async_table.columns

        assert result == ["col1", "col2", "col3"]

    def test_getitem_returns_async_column(self, mock_ibis_table):
        """Test that __getitem__ returns an AsyncIbisColumn."""
        async_table = AsyncIbisTable(mock_ibis_table, engine="postgres")
        mock_column = MagicMock()
        mock_ibis_table.__getitem__.return_value = mock_column

        result = async_table["col1"]

        assert isinstance(result, AsyncIbisColumn)
        assert result._engine == "postgres"

    def test_getitem_with_slice_returns_async_table(self, mock_ibis_table):
        """Test that __getitem__ with slice returns an AsyncIbisTable."""
        async_table = AsyncIbisTable(mock_ibis_table, engine="postgres")
        mock_sliced_expr = MagicMock()
        mock_ibis_table.__getitem__.return_value = mock_sliced_expr

        # Test slicing with offset and limit
        result = async_table[10:20]

        assert isinstance(result, AsyncIbisTable)
        assert result._engine == "postgres"
        mock_ibis_table.__getitem__.assert_called_once_with(slice(10, 20, None))


class TestAsyncIbisColumn:
    """Tests for AsyncIbisColumn class."""

    @pytest.mark.asyncio
    async def test_type_uses_thread(self):
        """Test that type() uses asyncio.to_thread."""
        mock_column = MagicMock()
        mock_column.type = MagicMock(return_value="int64")
        async_column = AsyncIbisColumn(mock_column, engine="postgres")

        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_to_thread:
            mock_to_thread.return_value = "int64"
            result = await async_column.type()

            assert result == "int64"
            mock_to_thread.assert_called_once_with(mock_column.type)

    def test_cast_returns_async_column(self):
        """Test that cast() returns an AsyncIbisColumn (lazy operation)."""
        mock_column = MagicMock()
        mock_new_column = MagicMock()
        mock_column.cast.return_value = mock_new_column
        async_column = AsyncIbisColumn(mock_column, engine="postgres")

        result = async_column.cast("string")

        assert isinstance(result, AsyncIbisColumn)
        assert result._engine == "postgres"


class TestEngineFlowThrough:
    """Tests for engine name flow through proxy chain."""

    @pytest.mark.asyncio
    async def test_engine_flows_from_connection_to_table(self, mock_ibis_connection):
        """Test that engine name flows from connection to table."""
        mock_table = MagicMock()
        mock_ibis_connection.table.return_value = mock_table

        async_conn = AsyncIbisConnection(mock_ibis_connection, engine="snowflake")
        async_table = await async_conn.table("test")

        assert async_table._engine == "snowflake"

    @pytest.mark.asyncio
    async def test_engine_flows_from_connection_to_table_via_sql(self, mock_ibis_connection):
        """Test that engine name flows from connection to table via sql()."""
        mock_expr = MagicMock()
        mock_ibis_connection.sql.return_value = mock_expr

        async_conn = AsyncIbisConnection(mock_ibis_connection, engine="snowflake")
        async_table = await async_conn.sql("SELECT 1")

        assert async_table._engine == "snowflake"

    def test_engine_flows_from_table_to_table_via_operations(self, mock_ibis_table):
        """Test that engine name flows from table to table via operations."""
        mock_expr = MagicMock()
        mock_ibis_table.select.return_value = mock_expr

        async_table = AsyncIbisTable(mock_ibis_table, engine="snowflake")
        result_table = async_table.select("col1")

        assert result_table._engine == "snowflake"

    def test_engine_flows_from_table_to_column(self, mock_ibis_table):
        """Test that engine name flows from table to column."""
        mock_column = MagicMock()
        mock_ibis_table.__getitem__.return_value = mock_column

        async_table = AsyncIbisTable(mock_ibis_table, engine="snowflake")
        async_column = async_table["col1"]

        assert async_column._engine == "snowflake"

    def test_engine_flows_through_chained_operations(self, mock_ibis_table):
        """Test that engine flows through chained lazy operations."""
        mock_expr1 = MagicMock()
        mock_expr2 = MagicMock()
        mock_expr3 = MagicMock()

        mock_ibis_table.select.return_value = mock_expr1
        mock_expr1.filter = MagicMock(return_value=mock_expr2)
        mock_expr2.limit = MagicMock(return_value=mock_expr3)

        async_table = AsyncIbisTable(mock_ibis_table, engine="mysql")
        result = async_table.select("col1").filter("col1 > 10").limit(100)

        assert result._engine == "mysql"


class TestLazyVsBlockingOperations:
    """Tests to verify lazy operations don't block and blocking operations do."""

    def test_lazy_operations_are_synchronous(self, mock_ibis_table):
        """Test that lazy operations are synchronous and don't require await."""
        async_table = AsyncIbisTable(mock_ibis_table, engine="postgres")

        # These should all be synchronous (no await needed)
        result1 = async_table.select("col1")
        result2 = async_table.limit(10)
        result3 = async_table.filter("col1 > 10")

        # All should be AsyncIbisTable instances
        assert isinstance(result1, AsyncIbisTable)
        assert isinstance(result2, AsyncIbisTable)
        assert isinstance(result3, AsyncIbisTable)

    @pytest.mark.asyncio
    async def test_blocking_operations_require_await(self, mock_ibis_table):
        """Test that blocking operations require await."""
        async_table = AsyncIbisTable(mock_ibis_table, engine="postgres")

        # These should all be asynchronous (require await)
        with patch("asyncio.to_thread", new_callable=AsyncMock):
            schema = await async_table.schema()
            result = await async_table.execute()

        # Verify they returned something (mocked)
        assert schema is not None
        assert result is not None
