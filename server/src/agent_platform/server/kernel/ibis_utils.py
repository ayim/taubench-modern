from __future__ import annotations

import asyncio
import typing
from typing import Any

from structlog import get_logger

if typing.TYPE_CHECKING:
    from agent_platform.core.data_connections.data_connections import DataConnection
    from agent_platform.core.payloads.data_connection import (
        DatabricksDataConnectionConfiguration,
        MySQLDataConnectionConfiguration,
        PostgresDataConnectionConfiguration,
        RedshiftDataConnectionConfiguration,
        SnowflakeCustomKeyPairConfiguration,
        SnowflakeDataConnectionConfiguration,
        SnowflakeLinkedConfiguration,
        SQLiteDataConnectionConfiguration,
    )
    from agent_platform.server.kernel.ibis_async_proxy import AsyncIbisConnection
logger = get_logger(__name__)


class DataConnectionInspectorError(Exception):
    """Base error raised when an error occurs in the data connection inspector."""


class ConnectionFailedError(DataConnectionInspectorError):
    """Error raised when unable to connect to a data source."""

    def __init__(self, message: str, details: str | None = None):
        self.message = message
        self.details = details
        full_message = message
        if details:
            full_message = f"{message}\n\nDetails: {details}"
        super().__init__(full_message)


class _ErrorPattern:
    """Represents a pattern for matching and formatting database errors."""

    def __init__(
        self,
        keywords: list[str],
        message_template: str,
        config_fields: list[str] | None = None,
        engine_specific: str | None = None,
        exclude_keywords: list[str] | None = None,
    ):
        self.keywords = keywords
        self.message_template = message_template
        self.config_fields = config_fields or []
        self.engine_specific = engine_specific
        self.exclude_keywords = exclude_keywords or []

    def matches(self, error_str_lower: str, engine: str) -> bool:
        """Check if this pattern matches the error string."""
        # Check engine-specific constraint
        if self.engine_specific and engine != self.engine_specific:
            return False

        # Check for excluded keywords
        if any(exclude in error_str_lower for exclude in self.exclude_keywords):
            return False

        # For single keyword, simple check
        if len(self.keywords) == 1:
            return self.keywords[0] in error_str_lower

        # For multiple keywords: if they seem related (like "database does not exist"),
        # require ALL to be present. Otherwise use OR logic.
        # Heuristic: if keywords contain common error phrases, use AND logic
        multi_word_patterns = ["does not exist", "not found", "is not"]
        if any(pattern in " ".join(self.keywords) for pattern in multi_word_patterns):
            return all(keyword in error_str_lower for keyword in self.keywords)

        # Otherwise use OR logic (any keyword matches)
        return any(keyword in error_str_lower for keyword in self.keywords)

    def format_message(self, config: Any, engine: str) -> str:
        """Format the error message with config values."""
        if not self.config_fields:
            return self.message_template

        values = {field: getattr(config, field, "unknown") for field in self.config_fields}
        return self.message_template.format(engine=engine, **values)


# Define error patterns in priority order (first match wins)
_ERROR_PATTERNS = [
    # Authentication errors (highest priority - check before generic connection errors)
    _ErrorPattern(
        keywords=[
            "authentication failed",
            "password authentication failed",
            "auth failed",
            "auth invalid",
            "password incorrect",
            "password wrong",
            "login failed",
            "invalid username",
            "access denied for user",
            "incorrect username or password",  # Snowflake-specific
        ],
        message_template=("Authentication failed for user '{user}'. Please check your username and password."),
        config_fields=["user"],
    ),
    # Snowflake-specific errors (check before generic patterns)
    _ErrorPattern(
        keywords=["warehouse", "does not exist"],
        message_template=(
            "Warehouse '{warehouse}' does not exist or is not accessible. "
            "Please verify the warehouse name and your permissions."
        ),
        config_fields=["warehouse"],
        engine_specific="snowflake",
    ),
    _ErrorPattern(
        keywords=["schema", "does not exist"],
        message_template=(
            "Schema '{schema}' does not exist or is not accessible. Please verify the schema name and your permissions."
        ),
        config_fields=["schema"],
        engine_specific="snowflake",
    ),
    _ErrorPattern(
        keywords=["role", "does not exist"],
        message_template=(
            "Role '{role}' does not exist or is not accessible. Please verify the role name and your permissions."
        ),
        config_fields=["role"],
        engine_specific="snowflake",
    ),
    _ErrorPattern(
        # Account identifier errors - must NOT contain username/password
        keywords=["account identifier"],
        message_template=("Invalid Snowflake account '{account}'. Please verify your account identifier is correct."),
        config_fields=["account"],
        engine_specific="snowflake",
        exclude_keywords=["username", "password"],
    ),
    # Connection refused
    _ErrorPattern(
        keywords=["connection refused"],
        message_template=(
            "Unable to connect to {engine} database at {host}:{port}. "
            "Please verify the host and port are correct and the database server is running."
        ),
        config_fields=["host", "port"],
    ),
    # Generic connection failed (but not auth-related)
    _ErrorPattern(
        keywords=["connection failed"],
        message_template=(
            "Unable to connect to {engine} database at {host}:{port}. "
            "Please verify the host and port are correct and the database server is running."
        ),
        config_fields=["host", "port"],
        exclude_keywords=["auth"],
    ),
    # Database does not exist
    _ErrorPattern(
        keywords=["database", "does not exist"],
        message_template=("Database '{database}' does not exist. Please verify the database name is correct."),
        config_fields=["database"],
    ),
    # Timeout
    _ErrorPattern(
        keywords=["timeout", "timed out"],
        message_template=("Connection timed out. Please check your network connection and firewall settings."),
    ),
    # Permission denied
    _ErrorPattern(
        keywords=["permission denied", "access denied"],
        message_template="Access denied. Please verify your credentials and database permissions.",
    ),
]


def _parse_connection_error(exception: Exception, engine: str, config: Any) -> str:
    """
    Parse database connection errors and return a user-friendly message.

    This function transforms verbose, technical database driver errors into
    concise, actionable messages for end users. Sensitive information like
    passwords is never included in the returned message.

    Args:
        exception: The original exception from the database driver
        engine: The database engine type (postgres, snowflake, redshift, sqlite)
        config: The connection configuration object

    Returns:
        A simplified, user-friendly error message that helps users understand
        and resolve the connection issue
    """
    error_str = str(exception)
    error_str_lower = error_str.lower()

    # Try to match against known error patterns
    for pattern in _ERROR_PATTERNS:
        if pattern.matches(error_str_lower, engine):
            return pattern.format_message(config, engine)

    # Fallback: extract meaningful error message
    lines = error_str.strip().split("\n")
    first_meaningful_line = lines[0] if lines else error_str

    # Limit length to avoid overwhelming the user
    max_error_length = 200
    if len(first_meaningful_line) > max_error_length:
        first_meaningful_line = first_meaningful_line[:max_error_length] + "..."

    return f"Connection failed: {first_meaningful_line}"


def _get_error_details(original_error: str, error_message: str) -> str | None:
    """
    Determine if error details should be included, avoiding duplication with error message.

    Args:
        original_error: The original error string from the exception
        error_message: The user-friendly error message

    Returns:
        The original error as details if it doesn't duplicate the error message, None otherwise
    """
    if not original_error:
        return None

    original_error_normalized = original_error.strip().lower()
    error_message_normalized = error_message.lower()

    # Only include details if they're different and original_error isn't contained in error_message
    if (
        original_error_normalized != error_message_normalized
        and original_error_normalized not in error_message_normalized
    ):
        return original_error

    return None


class IbisDbCallNotInWorkerThreadError(RuntimeError):
    pass


async def create_ibis_connection(data_connection: DataConnection) -> AsyncIbisConnection:
    """Create an ibis connection based on the data connection configuration.

    Returns an AsyncIbisConnection wrapper that provides a clean async API
    and integrates with the backend handler system for query execution.
    """
    from agent_platform.core.payloads.data_connection import (
        DatabricksDataConnectionConfiguration,
        MySQLDataConnectionConfiguration,
        PostgresDataConnectionConfiguration,
        RedshiftDataConnectionConfiguration,
        SnowflakeCustomKeyPairConfiguration,
        SnowflakeDataConnectionConfiguration,
        SnowflakeLinkedConfiguration,
        SQLiteDataConnectionConfiguration,
    )
    from agent_platform.server.kernel.ibis_async_proxy import AsyncIbisConnection

    engine = data_connection.engine
    config = data_connection.configuration

    if engine == "sqlite":
        conn = await _create_sqlite_connection(typing.cast(SQLiteDataConnectionConfiguration, config))
    elif engine == "postgres":
        conn = await _create_postgres_connection(typing.cast(PostgresDataConnectionConfiguration, config))
    elif engine == "mysql":
        conn = await _create_mysql_connection(typing.cast(MySQLDataConnectionConfiguration, config))
    elif engine == "redshift":
        conn = await _create_redshift_connection(typing.cast(RedshiftDataConnectionConfiguration, config))
    elif engine == "snowflake":
        conn = await _create_snowflake_connection(
            typing.cast(
                SnowflakeDataConnectionConfiguration
                | SnowflakeCustomKeyPairConfiguration
                | SnowflakeLinkedConfiguration,
                config,
            )
        )
    elif engine == "databricks":
        conn = await _create_databricks_connection(typing.cast(DatabricksDataConnectionConfiguration, config))
    else:
        raise ValueError(f"Unsupported engine for inspection: {engine}")

    # Add thread verification to prevent blocking calls in async context
    for attr, must_exist in [("_safe_raw_sql", False), ("execute", True)]:
        if not hasattr(conn, attr):
            if must_exist:
                raise ValueError(f"Connection object does not have attribute {attr}")
            continue
        _replace_method_with_thread_verification(conn, attr)

    # Wrap the connection in async proxy for clean async API
    # Use SQLite-specific wrapper for SQLite connections
    if engine == "sqlite":
        from agent_platform.server.kernel.ibis_async_proxy_sqlite import SqliteAsyncIbisConnection

        return SqliteAsyncIbisConnection(conn, engine=engine)
    else:
        return AsyncIbisConnection(conn, engine=engine)


def _replace_method_with_thread_verification(conn: Any, attr: str) -> None:
    import threading
    import weakref

    orig_weak_method = weakref.WeakMethod(getattr(conn, attr))  # Don't create a cycle!
    main_thread = threading.current_thread()

    def verify_thread_and_call_original(expr, *args, **kwargs):
        if main_thread == threading.current_thread():
            msg = (
                "Database calls through ibis must all be done in a worker thread, "
                "to avoid blocking the main asyncio event loop"
            )

            logger.error(msg, stack_info=True)
            raise IbisDbCallNotInWorkerThreadError(msg)
        original = orig_weak_method()
        if original is None:
            raise RuntimeError(f"The connection was already garbage collected. Unable to run {attr}.")
        return original(expr, *args, **kwargs)

    setattr(conn, attr, verify_thread_and_call_original)


async def _create_sqlite_connection(config: SQLiteDataConnectionConfiguration) -> Any:
    """Create SQLite ibis connection.

    Note: SQLite connections are created with check_same_thread=False to allow
    operations to run in worker threads (keeping the event loop responsive).
    SQLite's internal mutex provides thread-safety for concurrent access.
    """
    import sqlite3
    import time

    initial_time = time.monotonic()
    try:
        # Create SQLite connection in a worker thread with check_same_thread=False
        # This keeps the event loop responsive during file I/O
        def _create_sqlite_conn():
            sqlite_conn = sqlite3.connect(config.db_file, check_same_thread=False)
            # Use from_connection() to create ibis backend
            from ibis.backends.sqlite import Backend

            return Backend.from_connection(sqlite_conn)

        ret = await asyncio.to_thread(_create_sqlite_conn)
        logger.info(f"Created ibis.sqlite connection in {time.monotonic() - initial_time:.2f} seconds")
        return ret
    except ConnectionFailedError:
        raise
    except Exception as e:
        error_message = _parse_connection_error(e, "sqlite", config)
        details = _get_error_details(str(e), error_message)

        logger.error(
            "Failed to create sqlite connection",
            error=error_message,
            exc_info=True,
        )
        raise ConnectionFailedError(error_message, details=details) from e


async def _create_postgres_connection(config: PostgresDataConnectionConfiguration) -> Any:
    """Create PostgreSQL ibis connection."""
    import time

    import ibis

    initial_time = time.monotonic()
    try:
        ret = await asyncio.to_thread(
            ibis.postgres.connect,
            host=config.host,
            port=int(config.port),
            database=config.database,
            user=config.user,
            password=config.password,
            schema=config.schema,
        )
        logger.info(f"Created ibis.postgres connection in {time.monotonic() - initial_time:.2f} seconds")
        return ret
    except ConnectionFailedError:
        # Re-raise our own exceptions without modification
        raise
    except Exception as e:
        error_message = _parse_connection_error(e, "postgres", config)
        details = _get_error_details(str(e), error_message)

        logger.error(
            "Failed to create postgres connection",
            error=error_message,
            host=config.host,
            port=config.port,
            database=config.database,
            exc_info=True,
        )
        raise ConnectionFailedError(error_message, details=details) from e


async def _create_mysql_connection(config: MySQLDataConnectionConfiguration) -> Any:
    """Create MySQL ibis connection using mysqlclient driver.

    Note: Requires MySQL client libraries to be installed on the system.
    See docs/mysql-client-setup.md for installation instructions.
    """
    import time

    import ibis

    initial_time = time.monotonic()
    try:
        # Build connection parameters
        connect_params = {
            "host": config.host,
            "port": int(config.port),
            "database": config.database,
            "user": config.user,
            "password": config.password,
        }

        # Add SSL parameters if specified
        if config.ssl is not None:
            connect_params["ssl"] = config.ssl
        if config.ssl_ca is not None:
            connect_params["ssl_ca"] = config.ssl_ca
        if config.ssl_cert is not None:
            connect_params["ssl_cert"] = config.ssl_cert
        if config.ssl_key is not None:
            connect_params["ssl_key"] = config.ssl_key

        ret = await asyncio.to_thread(ibis.mysql.connect, **connect_params)
        logger.info(f"Created ibis.mysql connection in {time.monotonic() - initial_time:.2f} seconds")
        return ret
    except ConnectionFailedError:
        # Re-raise our own exceptions without modification
        raise
    except Exception as e:
        error_message = _parse_connection_error(e, "mysql", config)
        details = _get_error_details(str(e), error_message)

        logger.error(
            "Failed to create mysql connection",
            error=error_message,
            host=config.host,
            port=config.port,
            database=config.database,
            exc_info=True,
        )
        raise ConnectionFailedError(error_message, details=details) from e


async def _create_redshift_connection(config: RedshiftDataConnectionConfiguration) -> Any:
    """Create Redshift ibis connection."""
    import time

    import ibis

    from agent_platform.server.utils.redshift_utils import (
        patch_redshift_connection,
    )

    initial_time = time.monotonic()
    try:
        ret = await asyncio.to_thread(
            ibis.postgres.connect,
            host=config.host,
            port=int(config.port),
            database=config.database,
            user=config.user,
            password=config.password,
            schema=config.schema,
            # Redshift reports 'UNICODE' encoding, but psycopg needs 'utf-8'
            client_encoding="utf-8",
        )
        # Patch connection to work around Redshift incompatibilities
        ret = await asyncio.to_thread(patch_redshift_connection, ret)
        logger.info(f"Created ibis.redshift connection in {time.monotonic() - initial_time:.2f} seconds")
        return ret
    except ConnectionFailedError:
        raise
    except Exception as e:
        error_message = _parse_connection_error(e, "redshift", config)
        details = _get_error_details(str(e), error_message)

        logger.error(
            "Failed to create redshift connection",
            error=error_message,
            host=config.host,
            port=config.port,
            database=config.database,
            exc_info=True,
        )
        raise ConnectionFailedError(error_message, details=details) from e


async def _create_databricks_connection(config: DatabricksDataConnectionConfiguration) -> Any:
    """Create Databricks ibis connection"""
    import time

    import ibis

    initial_time = time.monotonic()
    try:
        ret = await asyncio.to_thread(
            ibis.databricks.connect,
            server_hostname=config.server_hostname,
            http_path=config.http_path,
            access_token=config.access_token,
            schema=config.schema,
            catalog=config.catalog,
        )
        logger.info(f"Created ibis.databricks connection in {time.monotonic() - initial_time:.2f} seconds")
        return ret
    except ConnectionFailedError:
        raise
    except Exception as e:
        error_message = _parse_connection_error(e, "databricks", config)
        details = _get_error_details(str(e), error_message)

        logger.error(
            "Failed to create databricks connection",
            error=error_message,
            server_hostname=config.server_hostname,
            http_path=config.http_path,
            exc_info=True,
        )
        raise ConnectionFailedError(error_message, details=details) from e


async def _validate_snowflake_database_schema_access(
    conn: Any,
    config: SnowflakeDataConnectionConfiguration | SnowflakeCustomKeyPairConfiguration | SnowflakeLinkedConfiguration,
) -> None:
    """Validate that the Snowflake role has access to the configured database and schema.

    Snowflake silently falls back to NULL database/schema when the role doesn't have
    USAGE (USE) privileges on the database or schema, rather than raising an error.
    This validation ensures the connection is actually usable with the specified
    database/schema.

    Args:
        conn: The ibis Snowflake connection to validate
        config: The connection configuration containing expected database/schema

    Raises:
        ConnectionFailedError: If the role cannot access the configured database/schema
    """

    def _check_access() -> None:
        result = conn.raw_sql("SELECT CURRENT_DATABASE(), CURRENT_SCHEMA()")
        try:
            row = result.fetchone()
        finally:
            close = getattr(result, "close", None)
            if callable(close):
                close()

        current_db, current_schema = row[0], row[1]

        if current_db is None:
            raise ConnectionFailedError(
                f"Cannot access database '{config.database}'. "
                f"The configured role does not have USE privileges on this database. "
                f"Please verify the role has access to the database or select a different role.",
                details=f"Expected database: {config.database}, but CURRENT_DATABASE() returned None",
            )

        if current_schema is None:
            raise ConnectionFailedError(
                f"Cannot access schema '{config.schema}' in database '{current_db}'. "
                f"The configured role does not have USE privileges on this schema. "
                f"Please verify the role has access to the schema or select a different role.",
                details=f"Expected schema: {config.schema}, but CURRENT_SCHEMA() returned None",
            )

        if current_db.upper() != config.database.upper():
            raise ConnectionFailedError(
                f"Database mismatch: expected '{config.database}' but connected to '{current_db}'. "
                f"This may indicate permission issues with the configured role.",
                details=f"Configured database: {config.database}, Actual: {current_db}",
            )

        if current_schema.upper() != config.schema.upper():
            raise ConnectionFailedError(
                f"Schema mismatch: expected '{config.schema}' but connected to '{current_schema}'. "
                f"This may indicate permission issues with the configured role.",
                details=f"Configured schema: {config.schema}, Actual: {current_schema}",
            )

    await asyncio.to_thread(_check_access)


async def _create_snowflake_connection(
    config: SnowflakeDataConnectionConfiguration | SnowflakeCustomKeyPairConfiguration | SnowflakeLinkedConfiguration,
) -> Any:
    """Create Snowflake ibis connection."""
    import time

    import ibis

    from agent_platform.core.payloads.data_connection import (
        SnowflakeCustomKeyPairConfiguration,
        SnowflakeLinkedConfiguration,
    )

    initial_time = time.monotonic()

    try:
        if isinstance(config, SnowflakeLinkedConfiguration):
            # Linked configuration - read auth from ~/.sema4ai/sf-auth.json
            from agent_platform.server.kernel.snowflake_auth_utils import (
                SnowflakeAuthError,
                get_snowflake_connection_params,
            )

            try:
                # Get connection parameters from auth file
                connection_params = await get_snowflake_connection_params(config)
                # Create ibis connection with the parameters
                ret = await asyncio.to_thread(ibis.snowflake.connect, **connection_params)
            except SnowflakeAuthError as e:
                # Convert SnowflakeAuthError to ConnectionFailedError
                raise ConnectionFailedError(str(e)) from e
        elif isinstance(config, SnowflakeCustomKeyPairConfiguration):
            # For custom key pair authentication
            # Load the private key from file and serialize to DER format
            # See: https://ibis-project.org/backends/snowflake#authenticating-with-key-pair-authentication
            from agent_platform.server.kernel.snowflake_auth_utils import (
                _load_private_key_from_file,
            )

            private_key_bytes = await asyncio.to_thread(
                _load_private_key_from_file,
                config.private_key_path,
                config.private_key_passphrase,
            )

            # Disable Arrow format to avoid compatibility issues with VARIANT/OBJECT types
            # Pass as kwargs to underlying snowflake connector
            ret = await asyncio.to_thread(
                ibis.snowflake.connect,
                account=config.account,
                user=config.user,
                private_key=private_key_bytes,
                warehouse=config.warehouse,
                database=config.database,
                schema=config.schema,
                role=config.role,
                session_parameters={
                    "PYTHON_CONNECTOR_QUERY_RESULT_FORMAT": "JSON",
                    "PYTHON_CONNECTOR_USE_NANOARROW": False,  # Disable nanoarrow (Arrow format)
                },
                use_pandas=False,  # Force JSON format, not Arrow
                create_object_udfs=False,  # We don't have any way to ask for this extra permission, disable it
                # to avoid noise.
            )
        else:
            # For password-based authentication
            ret = await asyncio.to_thread(
                ibis.snowflake.connect,
                account=config.account,
                user=config.user,
                password=config.password,
                warehouse=config.warehouse,
                database=config.database,
                schema=config.schema,
                role=config.role,
                session_parameters={
                    "PYTHON_CONNECTOR_QUERY_RESULT_FORMAT": "JSON",
                    "PYTHON_CONNECTOR_USE_NANOARROW": False,
                },
                use_pandas=False,
                create_object_udfs=False,  # We don't have any way to ask for this extra permission, disable it
                # to avoid noise.
            )

        elapsed = time.monotonic() - initial_time
        logger.info(f"Created ibis.snowflake connection in {elapsed:.2f} seconds")

        await _validate_snowflake_database_schema_access(ret, config)
        logger.info("Validated Snowflake database/schema access")

        return ret
    except ConnectionFailedError:
        raise
    except Exception as e:
        error_message = _parse_connection_error(e, "snowflake", config)
        details = _get_error_details(str(e), error_message)

        logger.error(
            "Failed to create snowflake connection",
            error=error_message,
            exc_info=True,
        )

        raise ConnectionFailedError(error_message, details=details) from e


def database_filter(database: str | None, schema: str | None = None) -> tuple[str, str] | str | None:
    """
    Filter database and schema for Ibis connection.

    Ibis support is either: database and schema, just schema, or none.
    """
    # Many DBMS support both a database and schema
    if database and schema:
        # Many DBMS support both a database and schema
        return (database, schema)
    elif schema:
        # Some DBMS just have one organizational unit (mysql, sqlite, impala)
        return schema

    return None
