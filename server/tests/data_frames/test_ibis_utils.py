import json
import sqlite3
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest

from agent_platform.server.kernel.ibis_utils import (
    ConnectionFailedError,
    create_ibis_connection,
)


@pytest.mark.asyncio
async def test_create_ibis_connection_sqlite(tmp_path: Path):
    """Test creating an ibis connection to SQLite."""

    from agent_platform.core.data_connections.data_connections import (
        DataConnection,
    )
    from agent_platform.core.payloads.data_connection import (
        SQLiteDataConnectionConfiguration,
    )

    # Create a SQLite database with some tables and data
    db_file = tmp_path / "test.db"
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()

    # Create tables
    cursor.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT, age INTEGER)")
    cursor.execute("CREATE TABLE orders (id INTEGER PRIMARY KEY, user_id INTEGER, amount REAL)")

    # Insert sample data
    cursor.execute("INSERT INTO users (name, age) VALUES ('Alice', 30)")
    cursor.execute("INSERT INTO users (name, age) VALUES ('Bob', 25)")
    cursor.execute("INSERT INTO users (name, age) VALUES ('Charlie', 35)")

    cursor.execute("INSERT INTO orders (user_id, amount) VALUES (1, 100.50)")
    cursor.execute("INSERT INTO orders (user_id, amount) VALUES (1, 200.75)")
    cursor.execute("INSERT INTO orders (user_id, amount) VALUES (2, 150.00)")

    conn.commit()
    conn.close()

    # Create a DataConnection object
    data_connection = DataConnection(
        id=str(uuid4()),
        name="test_sqlite_connection",
        description="Test SQLite connection",
        engine="sqlite",
        configuration=SQLiteDataConnectionConfiguration(db_file=str(db_file)),
        external_id=None,
        created_at=None,
        updated_at=None,
    )

    # Create ibis connection
    con = await create_ibis_connection(data_connection)

    # Perform SQL operations with ibis
    # 1. Simple SELECT query (now returns AsyncIbisTable)
    users_table = await con.sql("SELECT * FROM users")

    # Execute query using async API
    users_arrow = await users_table.to_pyarrow()
    users_result = users_arrow.to_pandas()

    assert len(users_result) == 3
    assert set(users_result["name"].tolist()) == {"Alice", "Bob", "Charlie"}

    # Test table operations with async API
    table = await con.table("users")
    schema = await table.schema()
    assert schema
    assert list(table.columns) == ["id", "name", "age"]
    column = table["age"]
    col_type = await column.type()
    assert col_type


@pytest.mark.asyncio
async def test_snowflake_keypair_file_not_found(tmp_path: Path):
    """Test that ValueError is raised when key file doesn't exist."""
    from agent_platform.core.data_connections.data_connections import (
        DataConnection,
    )
    from agent_platform.core.payloads.data_connection import (
        SnowflakeCustomKeyPairConfiguration,
    )
    from agent_platform.server.kernel.ibis_utils import (
        ConnectionFailedError,
    )

    data_connection = DataConnection(
        id=str(uuid4()),
        name="test_snowflake_connection",
        description="Test Snowflake connection",
        engine="snowflake",
        configuration=SnowflakeCustomKeyPairConfiguration(
            account="test-account",
            user="test-user",
            private_key_path="/nonexistent/path/to/key.p8",
            warehouse="test-warehouse",
            database="test-database",
            schema="test-schema",
        ),
        external_id=None,
        created_at=None,
        updated_at=None,
    )

    # Mock Path.home to prevent finding real sf-auth.json
    with patch("pathlib.Path.home", return_value=tmp_path):
        with pytest.raises(ConnectionFailedError) as exc_info:
            await create_ibis_connection(data_connection)

        # Check that the error message mentions the file not being found
        error_msg = str(exc_info.value).lower()
        assert "not found" in error_msg or "private key" in error_msg


@pytest.mark.asyncio
async def test_snowflake_keypair_invalid_key_format(tmp_path: Path):
    """Test that ValueError is raised when key has invalid format."""
    from agent_platform.core.data_connections.data_connections import (
        DataConnection,
    )
    from agent_platform.core.payloads.data_connection import (
        SnowflakeCustomKeyPairConfiguration,
    )
    from agent_platform.server.kernel.ibis_utils import (
        ConnectionFailedError,
    )

    # Create a file with invalid key data
    invalid_key_file = tmp_path / "invalid_key.pem"
    invalid_key_file.write_text("This is not a valid PEM key")

    data_connection = DataConnection(
        id=str(uuid4()),
        name="test_snowflake_connection",
        description="Test Snowflake connection",
        engine="snowflake",
        configuration=SnowflakeCustomKeyPairConfiguration(
            account="test-account",
            user="test-user",
            private_key_path=str(invalid_key_file),
            warehouse="test-warehouse",
            database="test-database",
            schema="test-schema",
        ),
        external_id=None,
        created_at=None,
        updated_at=None,
    )

    # Mock Path.home to prevent finding real sf-auth.json
    with patch("pathlib.Path.home", return_value=tmp_path):
        with pytest.raises(ConnectionFailedError) as exc_info:
            await create_ibis_connection(data_connection)

        # Check that the error is related to invalid key format
        error_msg = str(exc_info.value).lower()
        assert "invalid" in error_msg or "format" in error_msg or "key" in error_msg


@pytest.mark.asyncio
async def test_snowflake_keypair_wrong_passphrase(tmp_path: Path):
    """Test that ValueError is raised when wrong passphrase used."""
    from cryptography.hazmat.backends import default_backend
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    from agent_platform.core.data_connections.data_connections import (
        DataConnection,
    )
    from agent_platform.core.payloads.data_connection import (
        SnowflakeCustomKeyPairConfiguration,
    )
    from agent_platform.server.kernel.ibis_utils import (
        ConnectionFailedError,
    )

    # Generate a valid encrypted private key
    private_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048, backend=default_backend()
    )
    encrypted_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(b"correct_password"),
    )

    # Write encrypted key to file
    key_file = tmp_path / "encrypted_key.p8"
    key_file.write_bytes(encrypted_pem)

    data_connection = DataConnection(
        id=str(uuid4()),
        name="test_snowflake_connection",
        description="Test Snowflake connection",
        engine="snowflake",
        configuration=SnowflakeCustomKeyPairConfiguration(
            account="test-account",
            user="test-user",
            private_key_path=str(key_file),
            private_key_passphrase="wrong_password",
            warehouse="test-warehouse",
            database="test-database",
            schema="test-schema",
        ),
        external_id=None,
        created_at=None,
        updated_at=None,
    )

    # Mock Path.home to prevent finding real sf-auth.json
    with patch("pathlib.Path.home", return_value=tmp_path):
        with pytest.raises(ConnectionFailedError) as exc_info:
            await create_ibis_connection(data_connection)

        # Check that the error is related to passphrase
        error_msg = str(exc_info.value).lower()
        assert "passphrase" in error_msg or "password" in error_msg or "invalid" in error_msg


@pytest.mark.asyncio
async def test_snowflake_keypair_permission_denied(tmp_path: Path):
    """Test that ValueError is raised when permissions prevent reading."""
    import os
    import sys

    from agent_platform.core.data_connections.data_connections import (
        DataConnection,
    )
    from agent_platform.core.payloads.data_connection import (
        SnowflakeCustomKeyPairConfiguration,
    )
    from agent_platform.server.kernel.ibis_utils import (
        ConnectionFailedError,
    )

    # Skip on Windows as permission handling is different
    if sys.platform == "win32":
        pytest.skip("Permission test not applicable on Windows")

    # Create a file and remove read permissions
    key_file = tmp_path / "no_permission_key.pem"
    key_file.write_text("dummy key content")
    os.chmod(key_file, 0o000)  # Remove all permissions

    data_connection = DataConnection(
        id=str(uuid4()),
        name="test_snowflake_connection",
        description="Test Snowflake connection",
        engine="snowflake",
        configuration=SnowflakeCustomKeyPairConfiguration(
            account="test-account",
            user="test-user",
            private_key_path=str(key_file),
            warehouse="test-warehouse",
            database="test-database",
            schema="test-schema",
        ),
        external_id=None,
        created_at=None,
        updated_at=None,
    )

    try:
        with pytest.raises(ConnectionFailedError) as exc_info:
            await create_ibis_connection(data_connection)

        # Check that the error mentions permission
        error_msg = str(exc_info.value).lower()
        assert "permission" in error_msg or "denied" in error_msg
    finally:
        # Restore permissions for cleanup
        os.chmod(key_file, 0o644)


@pytest.mark.asyncio
async def test_snowflake_linked_missing_auth_file(tmp_path: Path):
    """Test error when auth file is missing."""
    from agent_platform.core.data_connections.data_connections import (
        DataConnection,
    )
    from agent_platform.core.payloads.data_connection import (
        SnowflakeLinkedConfiguration,
    )

    # Create a DataConnection object
    data_connection = DataConnection(
        id=str(uuid4()),
        name="test_snowflake_linked_missing",
        description="Test Snowflake linked connection with missing auth",
        engine="snowflake",
        configuration=SnowflakeLinkedConfiguration(
            warehouse="E2E_TESTS",
            database="TEST_DB",
            schema="PUBLIC",
        ),
        external_id=None,
        created_at=None,
        updated_at=None,
    )

    with patch("pathlib.Path.home", return_value=tmp_path):
        with pytest.raises(ConnectionFailedError) as exc_info:
            await create_ibis_connection(data_connection)

        assert "authentication file not found" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_snowflake_linked_missing_token_file(tmp_path: Path):
    """Test error when OAuth token file is missing."""
    from agent_platform.core.data_connections.data_connections import (
        DataConnection,
    )
    from agent_platform.core.payloads.data_connection import (
        SnowflakeLinkedConfiguration,
    )

    # Create mock auth file content for OAuth but without token file
    auth_data = {
        "type": "SNOWFLAKE_OAUTH_PARTNER",
        "linkingDetails": {
            "authenticator": "OAUTH",
            "account": "ZVZWMYO-PLATFORMTEAM",
            "role": "E2E_ENDUSER",
            "warehouse": "E2E_TESTS",
            "tokenPath": str(tmp_path / "nonexistent-token"),
        },
    }

    # Create a DataConnection object
    data_connection = DataConnection(
        id=str(uuid4()),
        name="test_snowflake_linked_missing_token",
        description="Test Snowflake linked with missing token",
        engine="snowflake",
        configuration=SnowflakeLinkedConfiguration(
            warehouse="E2E_TESTS",
            database="TEST_DB",
            schema="PUBLIC",
        ),
        external_id=None,
        created_at=None,
        updated_at=None,
    )

    # Mock the auth file path
    auth_file_path = tmp_path / ".sema4ai" / "sf-auth.json"
    auth_file_path.parent.mkdir(parents=True, exist_ok=True)
    auth_file_path.write_text(json.dumps(auth_data))

    with patch("pathlib.Path.home", return_value=tmp_path):
        with pytest.raises(ConnectionFailedError) as exc_info:
            await create_ibis_connection(data_connection)

        assert "token file not found" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_snowflake_linked_unsupported_authenticator(tmp_path: Path):
    """Test error when authenticator type is unsupported."""
    from agent_platform.core.data_connections.data_connections import (
        DataConnection,
    )
    from agent_platform.core.payloads.data_connection import (
        SnowflakeLinkedConfiguration,
    )

    # Create mock auth file with unsupported authenticator
    auth_data = {
        "type": "SNOWFLAKE_UNKNOWN",
        "linkingDetails": {
            "authenticator": "UNSUPPORTED_AUTH",
            "account": "ZVZWMYO-PLATFORMTEAM",
        },
    }

    # Create a DataConnection object
    data_connection = DataConnection(
        id=str(uuid4()),
        name="test_snowflake_linked_unsupported",
        description="Test Snowflake linked with unsupported auth",
        engine="snowflake",
        configuration=SnowflakeLinkedConfiguration(
            warehouse="E2E_TESTS",
            database="TEST_DB",
            schema="PUBLIC",
        ),
        external_id=None,
        created_at=None,
        updated_at=None,
    )

    # Mock the auth file path
    auth_file_path = tmp_path / ".sema4ai" / "sf-auth.json"
    auth_file_path.parent.mkdir(parents=True, exist_ok=True)
    auth_file_path.write_text(json.dumps(auth_data))

    with patch("pathlib.Path.home", return_value=tmp_path):
        with pytest.raises(ConnectionFailedError) as exc_info:
            await create_ibis_connection(data_connection)

        assert "unsupported authenticator" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_snowflake_linked_missing_account_oauth(tmp_path: Path):
    """Test error when account is missing in OAuth config."""
    from agent_platform.core.data_connections.data_connections import (
        DataConnection,
    )
    from agent_platform.core.payloads.data_connection import (
        SnowflakeLinkedConfiguration,
    )

    # Create mock auth file without account
    auth_data = {
        "type": "SNOWFLAKE_OAUTH_PARTNER",
        "linkingDetails": {
            "authenticator": "OAUTH",
            "tokenPath": str(tmp_path / "oauth-token"),
        },
    }

    # Create token file
    token_file = tmp_path / "oauth-token"
    token_file.write_text("mock_token")

    # Create a DataConnection object
    data_connection = DataConnection(
        id=str(uuid4()),
        name="test_snowflake_linked",
        description="Test Snowflake linked",
        engine="snowflake",
        configuration=SnowflakeLinkedConfiguration(
            warehouse="E2E_TESTS",
            database="TEST_DB",
            schema="PUBLIC",
        ),
        external_id=None,
        created_at=None,
        updated_at=None,
    )

    # Mock the auth file path
    auth_file_path = tmp_path / ".sema4ai" / "sf-auth.json"
    auth_file_path.parent.mkdir(parents=True, exist_ok=True)
    auth_file_path.write_text(json.dumps(auth_data))

    with patch("pathlib.Path.home", return_value=tmp_path):
        with pytest.raises(ConnectionFailedError) as exc_info:
            await create_ibis_connection(data_connection)

        assert "account not found" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_snowflake_linked_invalid_json(tmp_path: Path):
    """Test error when auth file contains invalid JSON."""
    from agent_platform.core.data_connections.data_connections import (
        DataConnection,
    )
    from agent_platform.core.payloads.data_connection import (
        SnowflakeLinkedConfiguration,
    )

    # Create a DataConnection object
    data_connection = DataConnection(
        id=str(uuid4()),
        name="test_snowflake_linked",
        description="Test Snowflake linked",
        engine="snowflake",
        configuration=SnowflakeLinkedConfiguration(
            warehouse="E2E_TESTS",
            database="TEST_DB",
            schema="PUBLIC",
        ),
        external_id=None,
        created_at=None,
        updated_at=None,
    )

    # Create auth file with invalid JSON
    auth_file_path = tmp_path / ".sema4ai" / "sf-auth.json"
    auth_file_path.parent.mkdir(parents=True, exist_ok=True)
    auth_file_path.write_text("{ invalid json }")

    with patch("pathlib.Path.home", return_value=tmp_path):
        with pytest.raises(ConnectionFailedError) as exc_info:
            await create_ibis_connection(data_connection)

        error_msg = str(exc_info.value).lower()
        assert "parse" in error_msg or "json" in error_msg
