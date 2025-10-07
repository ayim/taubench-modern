import typing
from typing import Any

from structlog import get_logger

if typing.TYPE_CHECKING:
    import pyarrow

    from agent_platform.core.data_connections.data_connections import DataConnection
    from agent_platform.core.payloads.data_connection import (
        ColumnInfo,
        DataConnectionsInspectRequest,
        DataConnectionsInspectResponse,
        PostgresDataConnectionConfiguration,
        RedshiftDataConnectionConfiguration,
        SnowflakeDataConnectionConfiguration,
        SQLiteDataConnectionConfiguration,
        TableInfo,
        TableToInspect,
    )

logger = get_logger(__name__)


class DataConnectionInspector:
    """Inspector for extracting metadata from data connections using ibis."""

    def __init__(self, data_connection: "DataConnection", request: "DataConnectionsInspectRequest"):
        self.data_connection = data_connection
        self.request = request

    async def inspect_connection(
        self,
    ) -> "DataConnectionsInspectResponse":
        """
        Inspect a data connection and return table/column metadata.

        Returns:
            DataConnectionsInspectResponse with table and column information
        """
        import time

        from agent_platform.core.payloads.data_connection import (
            DataConnectionsInspectResponse,
        )

        # Create ibis connection based on engine type
        connection = await self.create_ibis_connection(self.data_connection)

        # Get all tables if none specified
        if not self.request.tables_to_inspect:
            initial_time = time.monotonic()
            logger.info("Collecting tables to inspect")
            tables_to_inspect = await self._get_all_tables(connection)
            logger.info(f"Got all tables in {time.monotonic() - initial_time:.2f} seconds")
        else:
            tables_to_inspect = self.request.tables_to_inspect

        table_infos = []
        if self.request.inspect_columns:
            for i, table_spec in enumerate(tables_to_inspect):
                initial_time = time.monotonic()
                logger.info(
                    f"Inspecting table {table_spec.name} ({i + 1} of {len(tables_to_inspect)})"
                )
                table_info = await self._inspect_table(connection, table_spec)
                logger.info(
                    f"Inspected table {table_spec.name} ({i + 1} of {len(tables_to_inspect)}) in "
                    f"{time.monotonic() - initial_time:.2f} seconds"
                )
                table_infos.append(table_info)

        return DataConnectionsInspectResponse(tables=table_infos)

    @classmethod
    async def create_ibis_connection(cls, data_connection: "DataConnection") -> Any:
        """Create an ibis connection based on the data connection configuration."""
        from agent_platform.core.payloads.data_connection import (
            PostgresDataConnectionConfiguration,
            RedshiftDataConnectionConfiguration,
            SnowflakeDataConnectionConfiguration,
            SQLiteDataConnectionConfiguration,
        )

        engine = data_connection.engine
        config = data_connection.configuration

        if engine == "sqlite":
            return await cls._create_sqlite_connection(
                typing.cast(SQLiteDataConnectionConfiguration, config)
            )
        elif engine == "postgres":
            return await cls._create_postgres_connection(
                typing.cast(PostgresDataConnectionConfiguration, config)
            )
        elif engine == "redshift":
            return await cls._create_redshift_connection(
                typing.cast(RedshiftDataConnectionConfiguration, config)
            )
        elif engine == "snowflake":
            return await cls._create_snowflake_connection(
                typing.cast(SnowflakeDataConnectionConfiguration, config)
            )
        else:
            raise ValueError(f"Unsupported engine for inspection: {engine}")

    @classmethod
    async def _create_sqlite_connection(cls, config: "SQLiteDataConnectionConfiguration") -> Any:
        """Create SQLite ibis connection."""
        import time

        import ibis

        initial_time = time.monotonic()
        ret = ibis.sqlite.connect(config.db_file)
        logger.info(
            f"Created ibis.sqlite connection in {time.monotonic() - initial_time:.2f} seconds"
        )
        return ret

    @classmethod
    async def _create_postgres_connection(
        cls, config: "PostgresDataConnectionConfiguration"
    ) -> Any:
        """Create PostgreSQL ibis connection."""
        import time

        import ibis

        initial_time = time.monotonic()
        ret = ibis.postgres.connect(
            host=config.host,
            port=int(config.port),
            database=config.database,
            user=config.user,
            password=config.password,
            schema=config.schema,
        )
        logger.info(
            f"Created ibis.postgres connection in {time.monotonic() - initial_time:.2f} seconds"
        )
        return ret

    @classmethod
    async def _create_redshift_connection(
        cls, config: "RedshiftDataConnectionConfiguration"
    ) -> Any:
        """Create Redshift ibis connection."""
        import time

        import ibis

        initial_time = time.monotonic()
        ret = ibis.postgres.connect(
            host=config.host,
            port=int(config.port),
            database=config.database,
            user=config.user,
            password=config.password,
            schema=config.schema,
        )
        logger.info(
            f"Created ibis.redshift connection in {time.monotonic() - initial_time:.2f} seconds"
        )
        return ret

    @classmethod
    async def _create_snowflake_connection(
        cls, config: "SnowflakeDataConnectionConfiguration"
    ) -> Any:
        """Create Snowflake ibis connection."""
        # Commented out code (generated by the LLM: is this
        # really something that could be supported? --
        # SnowflakeDataConnectionConfiguration typing doesn't
        # really support it)
        # if config.credential_type == "custom-key-pair":
        #     # For custom key pair authentication
        #     return ibis.snowflake.connect(
        #         account=config.account,
        #         user=config.user,
        #         private_key_path=config.private_key_path,
        #         warehouse=config.warehouse,
        #         database=config.database,
        #         schema=config.schema,
        #         role=config.role,
        #         private_key_passphrase=config.private_key_passphrase,
        #     )
        # else:
        # For password-based authentication
        import time

        import ibis

        initial_time = time.monotonic()
        ret = ibis.snowflake.connect(
            account=config.account,
            user=config.user,
            password=config.password,
            warehouse=config.warehouse,
            database=config.database,
            schema=config.schema,
            role=config.role,
        )
        logger.info(
            f"Created ibis.snowflake connection in {time.monotonic() - initial_time:.2f} seconds"
        )
        return ret

    @classmethod
    async def _get_all_tables(cls, connection: Any) -> "list[TableToInspect]":
        """Get all tables from the connection."""
        from agent_platform.core.payloads.data_connection import TableToInspect

        # Get list of tables from ibis
        tables = connection.list_tables()

        table_specs = []
        for table_name in tables:
            # For most databases, we can get schema info from the connection
            schema = None
            database = None

            if hasattr(connection, "current_schema"):
                schema = connection.current_schema
            if hasattr(connection, "current_database"):
                database = connection.current_database

            table_specs.append(
                TableToInspect(
                    name=table_name,
                    database=database,
                    schema=schema,
                )
            )

        return table_specs

    def _select_with_limit(self, table, columns_to_inspect, n_sample_rows):
        """
        Note: extracted just so that we can mock it easily for testing
        purposes (to simulate errors when inspecting columns).
        """
        return table.select(columns_to_inspect).limit(n_sample_rows)

    async def _inspect_table(self, connection: Any, table_spec: "TableToInspect") -> "TableInfo":
        """Inspect a specific table and return its metadata."""
        import pyarrow

        from agent_platform.core.payloads.data_connection import TableInfo

        # Get the table reference
        table = connection.table(table_spec.name)

        # Get column information
        columns = []
        columns_to_inspect = []
        for column_name in table.schema().names:
            # Skip columns if specific columns are requested and this one isn't in the list
            if (
                table_spec.columns_to_inspect is not None
                and column_name not in table_spec.columns_to_inspect
            ):
                continue
            columns_to_inspect.append(column_name)

        sample_table: pyarrow.Table | dict[str, pyarrow.Table | None] | None = None
        if columns_to_inspect:
            # Execute query to get sample values
            try:
                sample_query = self._select_with_limit(
                    table, columns_to_inspect, self.request.n_sample_rows
                )

                sample_table_arrow: pyarrow.Table = sample_query.to_pyarrow()
                sample_table = sample_table_arrow
            except Exception as e:
                logger.error(f"Error inspecting table {table_spec.name}: {e!r}")

                # Ok, we haven't able to do a select with many columns (something went wrong),
                # let's try columns one by one -- note: this error can be expected if there's an
                # issue with the column type (for instance, if the column is an int but ibis
                # got it as a string).
                #
                # Example:
                # Error inspecting table film column release_year column type: unknown(
                #   DataType(this=Type.USERDEFINED, kind=year)): ArrowTypeError("Expected bytes,
                #   got a 'int' object")
                sample_table_dict: dict[str, pyarrow.Table | None] = {}
                for column_name in columns_to_inspect:
                    try:
                        sample_query = table.select(column_name).limit(self.request.n_sample_rows)
                        sample_table_dict[column_name] = sample_query.to_pyarrow()
                    except Exception as e:
                        logger.error(
                            f"Error inspecting table {table_spec.name} column {column_name} "
                            f"column type: {table[column_name].type()}: {e!r}"
                        )
                        sample_table_dict[column_name] = None
                sample_table = sample_table_dict

        for column_name in columns_to_inspect:
            column_info = await self._inspect_column(table, column_name, sample_table)
            columns.append(column_info)

        return TableInfo(
            name=table_spec.name,
            database=table_spec.database,
            schema=table_spec.schema,
            description=None,  # TODO: Add description extraction if available
            columns=columns,
        )

    async def _inspect_column(
        self,
        table: Any,
        column_name: str,
        sample_table: "pyarrow.Table | dict[str, pyarrow.Table | None] | None",
    ) -> "ColumnInfo":
        """Inspect a specific column and return its metadata."""
        from agent_platform.core.payloads.data_connection import ColumnInfo
        from agent_platform.server.data_frames.data_node import convert_to_valid_json_types

        # Get column type
        column_type = str(table[column_name].type())
        if sample_table is not None:
            if isinstance(sample_table, dict):
                sample_table = sample_table[column_name]

            if not sample_table:
                sample_values = None
            else:
                arrow_sample_values = sample_table[column_name].to_pylist()
                # Remove None values
                sample_values = [
                    convert_to_valid_json_types(v) for v in arrow_sample_values if v is not None
                ]
        else:
            sample_values = None

        return ColumnInfo(
            name=column_name,
            data_type=column_type,
            sample_values=sample_values,
            primary_key=None,  # TODO: Add primary key extraction if available
            unique=None,  # TODO: Add unique if available
            description=None,  # TODO: Add description extraction if available
            synonyms=None,  # TODO: Add synonyms if available
        )
