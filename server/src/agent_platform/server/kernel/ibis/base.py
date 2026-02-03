from __future__ import annotations

import asyncio
import typing
from abc import ABC, abstractmethod
from typing import Any, cast, overload

if typing.TYPE_CHECKING:
    import pandas
    import pyarrow
    from ibis.backends.sql import SQLBackend
    from ibis.expr.datatypes import DataType as IbisDataType
    from ibis.expr.schema import Schema as IbisSchema
    from ibis.expr.types import Column as IbisColumn
    from ibis.expr.types import Table as IbisTable


class AsyncIbisConnection(ABC):
    """Async wrapper for ibis connection objects.

    Wraps blocking connection methods with asyncio.to_thread() to prevent
    blocking the event loop. The engine name is stored and passed to child
    objects for backend-specific handling.

    Subclasses implement raw_sql() with typed cursor returns.

    Args:
        connection: Raw ibis connection object
        engine: Database engine name (e.g., 'snowflake', 'postgres', 'sqlite')
    """

    def __init__(self, connection: SQLBackend, engine: str):
        """Initialize async connection wrapper.

        Args:
            connection: Ibis backend connection (e.g., DuckDB, Snowflake, PostgreSQL backend)
            engine: Database engine name
        """
        self._connection = connection
        self._engine = engine

    @property
    def name(self) -> str:
        """Get the name of the underlying ibis backend.

        This is a direct property access (no I/O).

        Returns:
            Backend name (e.g., 'duckdb', 'snowflake', 'postgres')
        """
        return self._connection.name

    async def table(self, name: str, *, database: tuple[str, str] | str | None = None) -> AsyncIbisTable:
        """Get a table by name.

        This is a blocking I/O operation wrapped with asyncio.to_thread.

        Args:
            name: Table name
            database: Database/schema the table belongs to. Can be a string for
                single-level hierarchy (e.g. MySQL schema), a tuple of
                (catalog, database) for two-level hierarchy (e.g. Snowflake), or
                None if the RDBMS does not support any hierarchy.

        Returns:
            AsyncIbisTable wrapping the raw ibis table
        """
        raw_table = await asyncio.to_thread(self._connection.table, name, database=database)
        return AsyncIbisTable(raw_table, engine=self._engine)

    async def list_tables(self, *, database: tuple[str, str] | str | None = None) -> list[str]:
        """List all tables in the connection.

        This is a blocking I/O operation wrapped with asyncio.to_thread.

        Args:
            database: Database/schema the table belongs to. Can be a string for
                single-level hierarchy (e.g. MySQL schema), a tuple of
                (catalog, database) for two-level hierarchy (e.g. Snowflake), or
                None if the RDBMS does not support any hierarchy.

        Returns:
            List of table names
        """
        return await asyncio.to_thread(self._connection.list_tables, database=database)

    async def sql(self, query: str, dialect: str | None = None) -> AsyncIbisTable:
        """Execute a SQL query and return a table.

        This is a blocking I/O operation wrapped with asyncio.to_thread.

        Args:
            query: SQL query string
            dialect: SQL dialect (optional)

        Returns:
            AsyncIbisTable wrapping the result

        Raises:
            AttributeError: If the backend doesn't support sql method
        """
        raw_expr = await asyncio.to_thread(self._connection.sql, query, dialect=dialect)
        return AsyncIbisTable(raw_expr, engine=self._engine)

    async def create_table(self, name: str, obj: pyarrow.Table | pandas.DataFrame | Any) -> IbisTable:
        """Create a table from an object (e.g., PyArrow table, pandas DataFrame).

        This is a blocking I/O operation wrapped with asyncio.to_thread.

        Args:
            name: Name for the new table
            obj: Object to create table from (PyArrow Table, pandas DataFrame, etc.)

        Returns:
            The created table
        """
        return await asyncio.to_thread(self._connection.create_table, name, obj)

    async def get_current_schema(self) -> str:
        """Get the current schema name.

        This is a blocking I/O operation wrapped with asyncio.to_thread.
        Note: This property access may trigger I/O on some backends.

        Returns:
            Current schema name

        Note: this method will raise an exception for athena, bigquery, clickhouse, databricks, exasol,
        and polars. They do not have the concept for a "schema".
        """
        from ibis.backends import HasCurrentDatabase

        if not isinstance(self._connection, HasCurrentDatabase):
            raise ValueError("Engine does not have the concept of a schema.")

        hcd = cast(HasCurrentDatabase, self._connection)
        return await asyncio.to_thread(lambda: hcd.current_database)

    async def get_current_database(self) -> str:
        """Get the current database name.

        This is a blocking I/O operation wrapped with asyncio.to_thread.
        Note: This property access may trigger I/O on some backends.

        Returns:
            Current database name

        Note: this method will raise an exception for athena, bigquery, clickhouse, databricks, exasol,
        polars, impala, mysql, and sqlite. They have no concept of a "database".
        """
        from ibis.backends import HasCurrentCatalog

        if not isinstance(self._connection, HasCurrentCatalog):
            raise ValueError("Engine does not have the concept of a database.")

        hcc = cast(HasCurrentCatalog, self._connection)
        return await asyncio.to_thread(lambda: hcc.current_catalog)

    async def close(self) -> None:
        """Close the underlying ibis connection.

        This is a blocking I/O operation wrapped with asyncio.to_thread.
        Uses the SQLBackend.disconnect() method to properly close the connection.
        This ensures proper cleanup for backends that require explicit closing
        (e.g., PostgreSQL, Snowflake).
        """
        await asyncio.to_thread(self._connection.disconnect)

    @abstractmethod
    async def raw_sql(self, query: str, *, auto_commit: bool = True) -> Any:
        """Execute raw SQL and return a cursor.

        This is an async wrapper around the backend's raw_sql() method, which is
        available on all SQL backends (SQLite, PostgreSQL, MySQL, Snowflake, etc.).
        The caller is responsible for closing the cursor.

        Subclasses override this method to return properly typed cursors.

        This is a blocking I/O operation wrapped with asyncio.to_thread.

        Args:
            query: SQL query string
            auto_commit: If True (default), commit after execution. Set to False
                for explicit transaction control.

        Returns:
            A database cursor with the query results (type varies by backend)
        """
        ...

    @abstractmethod
    async def execute_dml(self, query: str, *, auto_commit: bool = True) -> int:
        """Execute a DML statement and return the affected row count.

        Use this for INSERT, UPDATE, DELETE statements where you need the
        affected row count but not the cursor itself.

        Handles backend-specific differences in how row counts are retrieved
        and ensures proper cursor cleanup.

        This is a blocking I/O operation wrapped with asyncio.to_thread.

        Args:
            query: DML statement (INSERT, UPDATE, or DELETE)
            auto_commit: If True (default), commit after execution. Set to False
                for explicit transaction control.

        Returns:
            Number of rows affected. Returns -1 if the count is unavailable.
        """
        ...


class AsyncIbisTable:
    """Async wrapper for ibis table objects.

    Wraps blocking table methods with asyncio.to_thread(). Lazy operations
    (expression building) are synchronous and just wrap the result.

    Args:
        table: Raw ibis table object
        engine: Database engine name for backend-specific handling
    """

    def __init__(self, table: IbisTable, engine: str):
        self._table = table
        self._engine = engine

    # Blocking operations (I/O)

    async def schema(self) -> IbisSchema:
        """Get the table schema.

        This is a blocking I/O operation wrapped with asyncio.to_thread.

        Returns:
            Table schema object
        """
        return await asyncio.to_thread(self._table.schema)

    async def execute_count(self) -> int:
        """Execute a count expression and return the integer result.

        This is a blocking I/O operation. Uses the backend handler system
        which handles backend-specific differences in count() return types.

        Returns:
            Count as integer
        """
        from agent_platform.server.semantic_data_models.handlers import (
            execute_count_with_backend_handler,
        )

        count_expr = self._table.count()

        return await execute_count_with_backend_handler(count_expr, engine=self._engine)

    async def to_pyarrow_unsafe(self) -> pyarrow.Table:
        """Convert table to PyArrow table WITHOUT dialect-specific transformations.

        WARNING: This method bypasses dialect-specific safety transformations!
        DO NOT USE DIRECTLY for user-facing data conversions.
        Use IbisTableAdapter.to_pyarrow() instead.

        This method performs a direct conversion to PyArrow without applying
        dialect-specific transformations that handle edge cases like:
        - Postgres NUMERIC (DECIMAL) columns containing NaN values
        - Other database-specific type conversion issues

        This is a blocking I/O operation. Uses the backend handler system
        to route to the appropriate handler (Snowflake, MySQL, etc.).


        Returns:
            PyArrow table (may have issues with certain data types)

        See Also:
            IbisTableAdapter.to_pyarrow() - Safe conversion with dialect handling
        """
        from agent_platform.server.semantic_data_models.handlers import (
            execute_query_with_backend_handler,
        )

        return await execute_query_with_backend_handler(self._table, engine=self._engine)

    async def execute(self) -> pandas.DataFrame | pandas.Series | Any:
        """Execute the table query.

        This is a blocking I/O operation wrapped with asyncio.to_thread.


        Returns:
            Query results (type varies by backend - may be DataFrame, scalar, or other types)
        """
        return await asyncio.to_thread(self._table.execute)

    async def to_pandas(self) -> pandas.DataFrame:
        """Convert table to pandas DataFrame.

        This is a blocking I/O operation wrapped with asyncio.to_thread.

        Returns:
            Pandas DataFrame
        """
        return await asyncio.to_thread(self._table.to_pandas)

    # Lazy operations (expression building, no I/O)

    def select(self, *args, **kwargs) -> AsyncIbisTable:
        """Select columns from the table.

        This is a lazy operation (no I/O). The expression is built immediately
        but not executed until a blocking operation like to_pyarrow() is called.

        Args:
            *args: Column names or expressions
            **kwargs: Additional arguments

        Returns:
            AsyncIbisTable wrapping the result
        """
        result = self._table.select(*args, **kwargs)
        return AsyncIbisTable(result, engine=self._engine)

    def limit(self, n: int) -> AsyncIbisTable:
        """Limit the number of rows.

        This is a lazy operation (no I/O).

        Args:
            n: Maximum number of rows

        Returns:
            AsyncIbisTable wrapping the result
        """
        result = self._table.limit(n)
        return AsyncIbisTable(result, engine=self._engine)

    def filter(self, *args, **kwargs) -> AsyncIbisTable:
        """Filter rows based on conditions.

        This is a lazy operation (no I/O).

        Args:
            *args: Filter conditions
            **kwargs: Additional arguments

        Returns:
            AsyncIbisTable wrapping the result
        """
        result = self._table.filter(*args, **kwargs)
        return AsyncIbisTable(result, engine=self._engine)

    def join(self, *args, **kwargs) -> AsyncIbisTable:
        """Join with another table.

        This is a lazy operation (no I/O).

        Args:
            *args: Join arguments
            **kwargs: Additional arguments

        Returns:
            AsyncIbisTable wrapping the result
        """
        result = self._table.join(*args, **kwargs)
        return AsyncIbisTable(result, engine=self._engine)

    def order_by(self, *args, **kwargs) -> AsyncIbisTable:
        """Order rows.

        This is a lazy operation (no I/O).

        Args:
            *args: Column names or expressions to order by
            **kwargs: Additional arguments

        Returns:
            AsyncIbisTable wrapping the result
        """
        result = self._table.order_by(*args, **kwargs)
        return AsyncIbisTable(result, engine=self._engine)

    def mutate(self, *args, **kwargs) -> AsyncIbisTable:
        """Add or modify columns.

        This is a lazy operation (no I/O).

        Args:
            *args: Column definitions
            **kwargs: Additional arguments

        Returns:
            AsyncIbisTable wrapping the result
        """
        result = self._table.mutate(*args, **kwargs)
        return AsyncIbisTable(result, engine=self._engine)

    def aggregate(self, *args, **kwargs) -> AsyncIbisTable:
        """Aggregate data.

        This is a lazy operation (no I/O).

        Args:
            *args: Aggregation expressions
            **kwargs: Additional arguments

        Returns:
            AsyncIbisTable wrapping the result
        """
        result = self._table.aggregate(*args, **kwargs)
        return AsyncIbisTable(result, engine=self._engine)

    def distinct(self, *args, **kwargs) -> AsyncIbisTable:
        """Get distinct rows.

        This is a lazy operation (no I/O).

        Args:
            *args: Column names (optional)
            **kwargs: Additional arguments

        Returns:
            AsyncIbisTable wrapping the result
        """
        result = self._table.distinct(*args, **kwargs)
        return AsyncIbisTable(result, engine=self._engine)

    def drop(self, *args, **kwargs) -> AsyncIbisTable:
        """Drop columns.

        This is a lazy operation (no I/O).

        Args:
            *args: Column names to drop
            **kwargs: Additional arguments

        Returns:
            AsyncIbisTable wrapping the result
        """
        result = self._table.drop(*args, **kwargs)
        return AsyncIbisTable(result, engine=self._engine)

    def union(self, *args, **kwargs) -> AsyncIbisTable:
        """Union with another table.

        This is a lazy operation (no I/O).

        Args:
            *args: Union arguments
            **kwargs: Additional arguments

        Returns:
            AsyncIbisTable wrapping the result
        """
        result = self._table.union(*args, **kwargs)
        return AsyncIbisTable(result, engine=self._engine)

    def intersect(self, *args, **kwargs) -> AsyncIbisTable:
        """Intersect with another table.

        This is a lazy operation (no I/O).

        Args:
            *args: Intersect arguments
            **kwargs: Additional arguments

        Returns:
            AsyncIbisTable wrapping the result
        """
        result = self._table.intersect(*args, **kwargs)
        return AsyncIbisTable(result, engine=self._engine)

    def alias(self, name: str) -> AsyncIbisTable:
        """Create an alias for the table.

        This is a lazy operation (no I/O).

        Args:
            name: Alias name

        Returns:
            AsyncIbisTable wrapping the result
        """
        result = self._table.alias(name)
        return AsyncIbisTable(result, engine=self._engine)

    def cast(self, *args, **kwargs) -> AsyncIbisTable:
        """Cast column types.

        This is a lazy operation (no I/O).

        Args:
            *args: Cast arguments
            **kwargs: Additional arguments

        Returns:
            AsyncIbisTable wrapping the result
        """
        result = self._table.cast(*args, **kwargs)
        return AsyncIbisTable(result, engine=self._engine)

    # Properties (cached, no I/O)

    @property
    def columns(self) -> tuple[str, ...]:
        """Get column names.

        This is a cached property (no I/O).

        Returns:
            List of column names
        """
        return self._table.columns

    @property
    def columns_with_types(self) -> dict[str, str]:
        """Get column names with their data types.

        This accesses the cached schema on the table expression.
        Unlike schema(), this is a sync property because the schema
        is cached on the Ibis table object after first access.

        Note: Both columns and columns_with_types exist because fetching
        type information may not be lazy for all backends.

        Returns:
            Mapping of column name to type string
        """
        schema = self._table.schema()
        return {name: str(dtype) for name, dtype in schema.items()}

    # Special methods

    @overload
    def __getitem__(self, key: str) -> AsyncIbisColumn: ...

    @overload
    def __getitem__(self, key: slice) -> AsyncIbisTable: ...

    def __getitem__(self, key: str | slice) -> AsyncIbisColumn | AsyncIbisTable:
        """Get a column by name or slice rows.

        This is a lazy operation (no I/O).

        Args:
            key: Column name (str) or row slice (slice object)

        Returns:
            AsyncIbisColumn if key is a string, AsyncIbisTable if key is a slice
        """
        if isinstance(key, slice):
            # Row slicing returns an expression
            return AsyncIbisTable(self._table[key], engine=self._engine)
        else:
            # Column access returns a column
            return AsyncIbisColumn(self._table[key], engine=self._engine)


class AsyncIbisColumn:
    """Async wrapper for ibis column objects.

    Wraps blocking column methods with asyncio.to_thread().

    Args:
        column: Raw ibis column object
        engine: Database engine name for backend-specific handling
    """

    def __init__(self, column: IbisColumn, engine: str):
        self._column = column
        self._engine = engine

    # Blocking operations (I/O)

    async def type(self) -> IbisDataType:
        """Get the column data type.

        This is a blocking I/O operation wrapped with asyncio.to_thread.

        Returns:
            Column data type
        """
        return await asyncio.to_thread(self._column.type)

    async def to_pyarrow(self) -> pyarrow.Array:
        """Convert column to PyArrow array.

        This is a blocking I/O operation wrapped with asyncio.to_thread.

        Returns:
            PyArrow array
        """
        return await asyncio.to_thread(self._column.to_pyarrow)

    # Lazy operations (expression building, no I/O)

    def cast(self, *args, **kwargs) -> AsyncIbisColumn:
        """Cast column to a different type.

        This is a lazy operation (no I/O).

        Args:
            *args: Cast arguments
            **kwargs: Additional arguments

        Returns:
            AsyncIbisColumn wrapping the result
        """
        result = self._column.cast(*args, **kwargs)
        return AsyncIbisColumn(result, engine=self._engine)

    def name(self, new_name: str) -> AsyncIbisColumn:
        """Rename/alias the column.

        This is a lazy operation (no I/O).

        Args:
            new_name: New name for the column

        Returns:
            AsyncIbisColumn wrapping the renamed column
        """
        result = self._column.name(new_name)
        return AsyncIbisColumn(cast("IbisColumn", result), engine=self._engine)

    def desc(self) -> IbisColumn:
        """Create descending sort expression.

        This is a lazy operation (no I/O).

        Returns:
            Raw ibis sort expression (used in order_by)
        """
        return self._column.desc()

    def asc(self) -> IbisColumn:
        """Create ascending sort expression.

        This is a lazy operation (no I/O).

        Returns:
            Raw ibis sort expression (used in order_by)
        """
        return self._column.asc()
