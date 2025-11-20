"""Unit tests for DataConnectionInspector error handling and parsing."""

import pytest


def test_parse_connection_refused_error():
    """Test parsing of connection refused errors."""
    from agent_platform.core.payloads.data_connection import (
        PostgresDataConnectionConfiguration,
    )
    from agent_platform.server.kernel.ibis_utils import (
        _parse_connection_error,
    )

    config = PostgresDataConnectionConfiguration(
        host="localhost",
        port=5432,
        database="test_db",
        user="test_user",
        password="test_password",
        schema="public",
    )

    class MockError(Exception):
        def __str__(self):
            return "Connection refused"

    result = _parse_connection_error(MockError(), "postgres", config)

    assert "Unable to connect to postgres database" in result
    assert "localhost:5432" in result
    assert "Please verify the host and port" in result
    assert "test_password" not in result  # Ensure password is not exposed


def test_parse_authentication_failed_error():
    """Test parsing of authentication failed errors."""
    from agent_platform.core.payloads.data_connection import (
        PostgresDataConnectionConfiguration,
    )
    from agent_platform.server.kernel.ibis_utils import (
        _parse_connection_error,
    )

    config = PostgresDataConnectionConfiguration(
        host="localhost",
        port=5432,
        database="test_db",
        user="test_user",
        password="test_password",
        schema="public",
    )

    class MockError(Exception):
        def __str__(self):
            return "password authentication failed for user test_user"

    result = _parse_connection_error(MockError(), "postgres", config)

    assert "Authentication failed for user 'test_user'" in result
    assert "Please check your username and password" in result
    assert "test_password" not in result


def test_parse_authentication_error_with_connection_failed_text():
    """Test that auth errors are detected even when they contain 'connection failed'."""
    from agent_platform.core.payloads.data_connection import (
        PostgresDataConnectionConfiguration,
    )
    from agent_platform.server.kernel.ibis_utils import (
        _parse_connection_error,
    )

    config = PostgresDataConnectionConfiguration(
        host="host.docker.internal",
        port=5433,
        database="test_db",
        user="wrong_user",
        password="wrong_password",
        schema="public",
    )

    # Simulate an error that contains both "connection failed" AND authentication failure
    class MockError(Exception):
        def __str__(self):
            return "connection failed: password authentication failed for user wrong_user"

    result = _parse_connection_error(MockError(), "postgres", config)

    # Should detect as authentication error, NOT as connection refused
    assert "Authentication failed for user 'wrong_user'" in result
    assert "Please check your username and password" in result
    assert "verify the host and port" not in result  # Should NOT suggest host/port issue
    assert "wrong_password" not in result


def test_parse_database_not_exist_error():
    """Test parsing of database does not exist errors."""
    from agent_platform.core.payloads.data_connection import (
        PostgresDataConnectionConfiguration,
    )
    from agent_platform.server.kernel.ibis_utils import (
        _parse_connection_error,
    )

    config = PostgresDataConnectionConfiguration(
        host="localhost",
        port=5432,
        database="nonexistent_db",
        user="test_user",
        password="test_password",
        schema="public",
    )

    class MockError(Exception):
        def __str__(self):
            return "database 'nonexistent_db' does not exist"

    result = _parse_connection_error(MockError(), "postgres", config)

    assert "Database 'nonexistent_db' does not exist" in result
    assert "Please verify the database name is correct" in result


def test_parse_timeout_error():
    """Test parsing of timeout errors."""
    from agent_platform.core.payloads.data_connection import (
        PostgresDataConnectionConfiguration,
    )
    from agent_platform.server.kernel.ibis_utils import (
        _parse_connection_error,
    )

    config = PostgresDataConnectionConfiguration(
        host="localhost",
        port=5432,
        database="test_db",
        user="test_user",
        password="test_password",
        schema="public",
    )

    class MockError(Exception):
        def __str__(self):
            return "Connection timed out after 30 seconds"

    result = _parse_connection_error(MockError(), "postgres", config)

    assert "Connection timed out" in result
    assert "Please check your network connection and firewall settings" in result


def test_parse_permission_denied_error():
    """Test parsing of permission denied errors."""
    from agent_platform.core.payloads.data_connection import (
        PostgresDataConnectionConfiguration,
    )
    from agent_platform.server.kernel.ibis_utils import (
        _parse_connection_error,
    )

    config = PostgresDataConnectionConfiguration(
        host="localhost",
        port=5432,
        database="test_db",
        user="test_user",
        password="test_password",
        schema="public",
    )

    class MockError(Exception):
        def __str__(self):
            return "Permission denied for schema public"

    result = _parse_connection_error(MockError(), "postgres", config)

    assert "Access denied" in result
    assert "Please verify your credentials and database permissions" in result


def test_parse_snowflake_incorrect_username_password():
    """Test parsing of Snowflake incorrect username or password errors."""
    from agent_platform.core.payloads.data_connection import (
        SnowflakeDataConnectionConfiguration,
    )
    from agent_platform.server.kernel.ibis_utils import (
        _parse_connection_error,
    )

    config = SnowflakeDataConnectionConfiguration(
        account="zvzwmyo-hp00956",
        user="wrong_user",
        password="wrong_password",
        warehouse="test_warehouse",
        database="test_db",
        schema="public",
        role="PUBLIC",
    )

    class MockError(Exception):
        def __str__(self):
            return (
                "250001 (08001): None: Failed to connect to DB: "
                "zvzwmyo-hp00956.snowflakecomputing.com:443. "
                "Incorrect username or password was specified."
            )

    result = _parse_connection_error(MockError(), "snowflake", config)

    # Should be recognized as authentication error, NOT account error
    assert "Authentication failed for user 'wrong_user'" in result
    assert "Please check your username and password" in result
    assert "account identifier" not in result.lower()
    assert "wrong_password" not in result


def test_parse_snowflake_schema_not_exist():
    """Test parsing of Snowflake schema does not exist errors."""
    from agent_platform.core.payloads.data_connection import (
        SnowflakeDataConnectionConfiguration,
    )
    from agent_platform.server.kernel.ibis_utils import (
        _parse_connection_error,
    )

    config = SnowflakeDataConnectionConfiguration(
        account="test_account",
        user="test_user",
        password="test_password",
        warehouse="test_warehouse",
        database="test_db",
        schema="INVALID_SCHEMA",
        role="PUBLIC",
    )

    class MockError(Exception):
        def __str__(self):
            return "Schema 'INVALID_SCHEMA' does not exist or not authorized."

    result = _parse_connection_error(MockError(), "snowflake", config)

    assert "Schema 'INVALID_SCHEMA' does not exist or is not accessible" in result
    assert "Please verify the schema name and your permissions" in result


def test_parse_snowflake_role_not_exist():
    """Test parsing of Snowflake role does not exist errors."""
    from agent_platform.core.payloads.data_connection import (
        SnowflakeDataConnectionConfiguration,
    )
    from agent_platform.server.kernel.ibis_utils import (
        _parse_connection_error,
    )

    config = SnowflakeDataConnectionConfiguration(
        account="test_account",
        user="test_user",
        password="test_password",
        warehouse="test_warehouse",
        database="test_db",
        schema="public",
        role="INVALID_ROLE",
    )

    class MockError(Exception):
        def __str__(self):
            return "Role 'INVALID_ROLE' does not exist or not authorized."

    result = _parse_connection_error(MockError(), "snowflake", config)

    assert "Role 'INVALID_ROLE' does not exist or is not accessible" in result
    assert "Please verify the role name and your permissions" in result


def test_parse_snowflake_invalid_account_error():
    """Test parsing of Snowflake invalid account errors."""
    from agent_platform.core.payloads.data_connection import (
        SnowflakeDataConnectionConfiguration,
    )
    from agent_platform.server.kernel.ibis_utils import (
        _parse_connection_error,
    )

    config = SnowflakeDataConnectionConfiguration(
        account="invalid_account",
        user="test_user",
        password="test_password",
        warehouse="test_warehouse",
        database="test_db",
        schema="public",
        role="PUBLIC",
    )

    class MockError(Exception):
        def __str__(self):
            return "Invalid account identifier: invalid_account"

    result = _parse_connection_error(MockError(), "snowflake", config)

    assert "Invalid Snowflake account 'invalid_account'" in result
    assert "Please verify your account identifier is correct" in result
    assert "test_password" not in result


def test_parse_snowflake_warehouse_not_exist_error():
    """Test parsing of Snowflake warehouse does not exist errors."""
    from agent_platform.core.payloads.data_connection import (
        SnowflakeDataConnectionConfiguration,
    )
    from agent_platform.server.kernel.ibis_utils import (
        _parse_connection_error,
    )

    config = SnowflakeDataConnectionConfiguration(
        account="test_account",
        user="test_user",
        password="test_password",
        warehouse="nonexistent_warehouse",
        database="test_db",
        schema="public",
        role="PUBLIC",
    )

    class MockError(Exception):
        def __str__(self):
            return "Warehouse 'nonexistent_warehouse' does not exist or is not accessible"

    result = _parse_connection_error(MockError(), "snowflake", config)

    assert "Warehouse 'nonexistent_warehouse' does not exist or is not accessible" in result
    assert "Please verify the warehouse name and your permissions" in result


def test_parse_unknown_error_truncates_long_messages():
    """Test that unknown errors are truncated when too long."""
    from agent_platform.core.payloads.data_connection import (
        PostgresDataConnectionConfiguration,
    )
    from agent_platform.server.kernel.ibis_utils import (
        _parse_connection_error,
    )

    config = PostgresDataConnectionConfiguration(
        host="localhost",
        port=5432,
        database="test_db",
        user="test_user",
        password="test_password",
        schema="public",
    )

    # Create a very long error message
    long_message = "x" * 250

    class MockError(Exception):
        def __str__(self):
            return long_message

    result = _parse_connection_error(MockError(), "postgres", config)

    assert "Connection failed:" in result
    # Should be truncated to max_error_length + "Connection failed: " + "..."
    assert len(result) <= 225
    assert result.endswith("...")


def test_parse_unknown_error_uses_first_line():
    """Test that unknown multiline errors only show first line."""
    from agent_platform.core.payloads.data_connection import (
        PostgresDataConnectionConfiguration,
    )
    from agent_platform.server.kernel.ibis_utils import (
        _parse_connection_error,
    )

    config = PostgresDataConnectionConfiguration(
        host="localhost",
        port=5432,
        database="test_db",
        user="test_user",
        password="test_password",
        schema="public",
    )

    class MockError(Exception):
        def __str__(self):
            return "First line of error\nSecond line\nThird line"

    result = _parse_connection_error(MockError(), "postgres", config)

    assert "Connection failed: First line of error" in result
    assert "Second line" not in result
    assert "Third line" not in result


def test_connection_failed_error_message_formatting():
    """Test that ConnectionFailedError is properly formatted for connection failures."""
    from agent_platform.core.payloads.data_connection import (
        PostgresDataConnectionConfiguration,
    )
    from agent_platform.server.kernel.ibis_utils import (
        _parse_connection_error,
    )

    config = PostgresDataConnectionConfiguration(
        host="localhost",
        port=9999,
        database="test_db",
        user="test_user",
        password="test_password",
        schema="public",
    )

    class MockConnectionError(Exception):
        def __str__(self):
            return "Connection refused"

    result = _parse_connection_error(MockConnectionError(), "postgres", config)

    assert "Unable to connect to postgres database" in result
    assert "localhost:9999" in result
    assert "test_password" not in result  # Ensure password is not exposed


def test_connection_failed_error_exception_properties():
    """Test ConnectionFailedError exception properties."""
    from agent_platform.server.kernel.ibis_utils import (
        ConnectionFailedError,
        DataConnectionInspectorError,
    )

    # Test basic initialization
    error = ConnectionFailedError("Unable to connect")
    assert str(error) == "Unable to connect"
    assert isinstance(error, DataConnectionInspectorError)
    assert isinstance(error, Exception)

    # Test with details
    error_with_details = ConnectionFailedError("Unable to connect", "Port is closed")
    error_str = str(error_with_details)
    assert "Unable to connect" in error_str
    assert "Port is closed" in error_str


def test_table_not_found_error_has_correct_attributes():
    """Test TableNotFoundError has correct attributes and message."""
    from agent_platform.server.kernel.data_connection_inspector import (
        TableNotFoundError,
    )

    error = TableNotFoundError("my_table", "Table does not exist in database")

    assert error.table_name == "my_table"
    assert error.details == "Table does not exist in database"
    assert "my_table" in str(error)
    assert "not found" in str(error)


def test_parse_connection_error_handles_config_without_host():
    """Test that error parsing handles configs without host attribute gracefully."""
    from agent_platform.core.payloads.data_connection import (
        SQLiteDataConnectionConfiguration,
    )
    from agent_platform.server.kernel.ibis_utils import (
        _parse_connection_error,
    )

    config = SQLiteDataConnectionConfiguration(db_file="/path/to/db.sqlite")

    class MockError(Exception):
        def __str__(self):
            return "Connection refused"

    result = _parse_connection_error(MockError(), "sqlite", config)

    # Should handle missing host/port gracefully
    assert "unknown" in result or "Connection failed" in result


def test_parse_error_preserves_exception_chain():
    """Test that ConnectionFailedError preserves the original exception chain."""
    from agent_platform.server.kernel.ibis_utils import (
        ConnectionFailedError,
    )

    original_error = ValueError("Original database error")

    # Helper function to raise the chained exception
    def raise_chained_error():
        try:
            raise original_error
        except ValueError as e:
            raise ConnectionFailedError("Friendly message") from e

    with pytest.raises(ConnectionFailedError) as exc_info:
        raise_chained_error()

    assert exc_info.value.__cause__ is original_error
    assert isinstance(exc_info.value.__cause__, ValueError)
