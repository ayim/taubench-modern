from datetime import datetime

import pytest

from agent_platform.core.data_server.data_server import (
    DataServerDetails,
    DataServerEndpoint,
    DataServerEndpointKind,
)
from agent_platform.core.utils import SecretString


class TestDataServerDetails:
    """Test API connection details behavior with minimal parsing."""

    def test_connection_details_missing_required_fields(self):
        """Test that host and port are required fields."""
        # Test missing both host and port
        with pytest.raises(
            TypeError, match="missing 2 required positional arguments: 'host' and 'port'"
        ):
            DataServerEndpoint()  # type: ignore[call-arg]

        # Test missing port only
        with pytest.raises(TypeError, match="missing 1 required positional argument: 'port'"):
            DataServerEndpoint(host="example.com")  # type: ignore[call-arg]

        # Test missing host only
        with pytest.raises(TypeError, match="missing 1 required positional argument: 'host'"):
            DataServerEndpoint(port=8080)  # type: ignore[call-arg]

    def test_connection_details_basic_host(self):
        """Test connection details with explicit host and port."""
        conn = DataServerEndpoint(host="example.com", port=8000)
        assert conn.host == "example.com"
        assert conn.port == 8000
        assert conn.kind == DataServerEndpointKind.HTTP
        assert conn.full_address == "example.com:8000"

    def test_connection_details_with_explicit_port(self):
        """Test connection details with explicit port parameter."""
        conn = DataServerEndpoint(host="example.com", port=9001)
        assert conn.host == "example.com"
        assert conn.port == 9001
        assert conn.full_address == "example.com:9001"

    def test_connection_details_mysql_kind(self):
        """Test connection details with MySQL kind and explicit port."""
        conn = DataServerEndpoint(
            host="mysql.example.com", port=3306, kind=DataServerEndpointKind.MYSQL
        )
        assert conn.host == "mysql.example.com"
        assert conn.port == 3306
        assert conn.kind == DataServerEndpointKind.MYSQL
        assert conn.full_address == "mysql.example.com:3306"

    def test_connection_details_mysql_with_custom_port(self):
        """Test MySQL connection with custom port."""
        conn = DataServerEndpoint(
            host="mysql.example.com", kind=DataServerEndpointKind.MYSQL, port=3307
        )
        assert conn.host == "mysql.example.com"
        assert conn.port == 3307
        assert conn.kind == DataServerEndpointKind.MYSQL
        assert conn.full_address == "mysql.example.com:3307"

    def test_connection_details_empty_host_validation(self):
        """Test that empty or whitespace-only host values are rejected."""
        # Test empty string host should fail validation
        with pytest.raises(ValueError, match="Host cannot be empty"):
            DataServerEndpoint(host="", port=8000)

        # Test whitespace-only host should fail validation
        with pytest.raises(ValueError, match="Host cannot be empty"):
            DataServerEndpoint(host="   ", port=8000)

    def test_connection_details_invalid_port_validation(self):
        """Test that invalid port values are rejected."""
        # Test zero port
        with pytest.raises(ValueError, match="Port must be a positive integer"):
            DataServerEndpoint(host="example.com", port=0)

        # Test negative port
        with pytest.raises(ValueError, match="Port must be a positive integer"):
            DataServerEndpoint(host="example.com", port=-1)

        # Test very negative port
        with pytest.raises(ValueError, match="Port must be a positive integer"):
            DataServerEndpoint(host="example.com", port=-8080)

    def test_model_dump(self):
        """Test model_dump returns correct dictionary."""
        conn = DataServerEndpoint(host="example.com", port=9000, kind=DataServerEndpointKind.MYSQL)
        dump = conn.model_dump()
        assert dump == {
            "kind": "mysql",
            "host": "example.com",
            "port": 9000,
        }

    def test_model_validate(self):
        """Test model_validate creates instance from dictionary."""
        data = {
            "kind": "http",
            "host": "api.example.com",
            "port": 8080,
        }
        conn = DataServerEndpoint.model_validate(data)

        # Verify the instance was created correctly
        assert conn.host == "api.example.com"
        assert conn.port == 8080
        assert conn.kind == DataServerEndpointKind.HTTP
        assert conn.full_address == "api.example.com:8080"

    def test_model_validate_missing_required_fields(self):
        """Test model_validate with missing required fields fails properly."""
        # Test missing port
        data = {"host": "example.com"}
        with pytest.raises(TypeError, match="missing 1 required positional argument: 'port'"):
            DataServerEndpoint.model_validate(data)

        # Test missing host
        data = {"port": 8000}
        with pytest.raises(TypeError, match="missing 1 required positional argument: 'host'"):
            DataServerEndpoint.model_validate(data)

        # Test missing both
        data = {"kind": "http"}
        with pytest.raises(
            TypeError, match="missing 2 required positional arguments: 'host' and 'port'"
        ):
            DataServerEndpoint.model_validate(data)

    def test_model_validate_invalid_values(self):
        """Test model_validate with invalid host and port values fails properly."""
        # Test empty host through model_validate
        data = {"host": "", "port": 8000}
        with pytest.raises(ValueError, match="Host cannot be empty"):
            DataServerEndpoint.model_validate(data)

        # Test whitespace host through model_validate
        data = {"host": "   ", "port": 8000}
        with pytest.raises(ValueError, match="Host cannot be empty"):
            DataServerEndpoint.model_validate(data)

        # Test invalid port through model_validate
        data = {"host": "example.com", "port": 0}
        with pytest.raises(ValueError, match="Port must be a positive integer"):
            DataServerEndpoint.model_validate(data)

        # Test negative port through model_validate
        data = {"host": "example.com", "port": -1}
        with pytest.raises(ValueError, match="Port must be a positive integer"):
            DataServerEndpoint.model_validate(data)

    def test_model_validate_roundtrip(self):
        """Test that model_dump -> model_validate is a roundtrip."""
        original = DataServerEndpoint(
            host="example.com", port=7777, kind=DataServerEndpointKind.MYSQL
        )
        dumped = original.model_dump()
        restored = DataServerEndpoint.model_validate(dumped)

        assert restored.host == "example.com"
        assert restored.port == 7777
        assert restored.kind == DataServerEndpointKind.MYSQL
        assert restored.full_address == "example.com:7777"


class TestDataServerEndpoint:
    """Test SecretString handling and serialization in DataServerEndpoint."""

    def test_secret_string_conversion_from_string(self):
        """Test automatic conversion of string password to SecretString and updated_at default."""
        connection = DataServerEndpoint(host="api.example.com", port=8080)

        before_creation = datetime.now()
        creds = DataServerDetails(
            username="testuser",
            password="secret123",  # type: ignore[arg-type] # String password
            data_server_endpoints=[connection],
        )
        after_creation = datetime.now()

        # Test SecretString conversion
        assert isinstance(creds.password, SecretString)
        assert creds.password is not None
        assert creds.password.get_secret_value() == "secret123"
        assert str(creds.password) == "**********"

        # Test updated_at field gets default value
        assert isinstance(creds.updated_at, datetime)
        assert before_creation <= creds.updated_at <= after_creation

    def test_secret_string_already_secret_string(self):
        """Test that existing SecretString is preserved and explicit updated_at works."""
        connection = DataServerEndpoint(
            host="mysql.example.com", port=3306, kind=DataServerEndpointKind.MYSQL
        )
        secret_password = SecretString("secret123")
        specific_time = datetime(2024, 1, 15, 10, 30, 45)

        creds = DataServerDetails(
            username="testuser",
            password=secret_password,
            data_server_endpoints=[connection],
            updated_at=specific_time,
        )

        # Test SecretString preservation
        assert isinstance(creds.password, SecretString)
        assert creds.password is not None
        assert creds.password.get_secret_value() == "secret123"
        assert creds.password is secret_password  # Same object

        # Test explicit updated_at setting
        assert creds.updated_at == specific_time

    def test_model_dump_serializes_secret_string(self):
        """Test model_dump properly serializes SecretString."""
        connection = DataServerEndpoint(host="api.example.com", port=8080)

        creds = DataServerDetails(
            username="testuser",
            password="secret123",  # type: ignore[arg-type]
            data_server_endpoints=[connection],
        )

        dump = creds.model_dump()

        assert dump["username"] == "testuser"
        assert isinstance(dump["password"], SecretString)
        assert dump["password"].get_secret_value() == "secret123"
        assert str(dump["password"]) == "**********"

        assert dump["data_server_endpoints"] == [
            {
                "kind": "http",
                "host": "api.example.com",
                "port": 8080,
            }
        ]

    def test_as_datasource_connection_input_http(self):
        """Test as_datasource_connection_input for HTTP connection."""
        connection = DataServerEndpoint(host="api.example.com", port=8080)

        creds = DataServerDetails(
            username="testuser",
            password="secret123",  # type: ignore[arg-type]
            data_server_endpoints=[connection],
        )

        datasource_input = creds.as_datasource_connection_input()

        expected = {
            "http": {
                "url": "http://api.example.com:8080",
                "port": 8080,
                "user": "testuser",
                "password": "secret123",
            },
        }

        assert datasource_input == expected

    def test_as_datasource_connection_input_mysql(self):
        """Test as_datasource_connection_input for MySQL connection."""
        connection = DataServerEndpoint(
            host="mysql.example.com", port=3307, kind=DataServerEndpointKind.MYSQL
        )

        creds = DataServerDetails(
            username="testuser",
            password="secret123",  # type: ignore[arg-type]
            data_server_endpoints=[connection],
        )

        datasource_input = creds.as_datasource_connection_input()

        expected = {
            "mysql": {
                "host": "mysql.example.com",
                "port": 3307,
                "user": "testuser",
                "password": "secret123",
            },
        }

        assert datasource_input == expected

    def test_as_datasource_connection_input_multiple_connections(self):
        """Test as_datasource_connection_input with both HTTP and MySQL connections."""
        http_connection = DataServerEndpoint(
            host="api.example.com", port=8080, kind=DataServerEndpointKind.HTTP
        )
        mysql_connection = DataServerEndpoint(
            host="mysql.example.com", port=3307, kind=DataServerEndpointKind.MYSQL
        )

        creds = DataServerDetails(
            username="testuser",
            password="secret123",  # type: ignore[arg-type]
            data_server_endpoints=[http_connection, mysql_connection],
        )

        datasource_input = creds.as_datasource_connection_input()

        expected = {
            "http": {
                "url": "http://api.example.com:8080",
                "port": 8080,
                "user": "testuser",
                "password": "secret123",
            },
            "mysql": {
                "host": "mysql.example.com",
                "port": 3307,
                "user": "testuser",
                "password": "secret123",
            },
        }

        assert datasource_input == expected

    def test_secret_string_not_leaked_in_repr(self):
        """Test that SecretString values are not leaked in string representations."""
        connection = DataServerEndpoint(host="localhost", port=8000)

        creds = DataServerDetails(
            username="testuser",
            password="secret123",  # type: ignore[arg-type]
            data_server_endpoints=[connection],
        )

        # Check that secret is not in string representation
        creds_str = str(creds)
        creds_repr = repr(creds)

        assert "secret123" not in creds_str
        assert "secret123" not in creds_repr
        assert "**********" in creds_repr

    def test_model_validate_with_secret_string(self):
        """Test model_validate handles SecretString objects correctly."""
        secret_password = SecretString("secret123")
        data = {
            "username": "testuser",
            "password": secret_password,
            "data_server_connections": [
                {
                    "kind": "http",
                    "host": "api.example.com",
                    "port": 8080,
                }
            ],
        }

        creds = DataServerDetails.model_validate(data)

        assert creds.username == "testuser"
        assert isinstance(creds.password, SecretString)
        assert creds.password is not None
        assert creds.password.get_secret_value() == "secret123"
        assert creds.password is secret_password  # Should preserve the same object

    def test_model_validate_with_nested_objects(self):
        """Test model_validate handles pre-constructed nested objects."""
        connection = DataServerEndpoint(host="api.example.com", port=8080)

        data = {
            "username": "testuser",
            "password": "secret123",
            "data_server_connections": [connection],
        }

        creds = DataServerDetails.model_validate(data)

        assert creds.username == "testuser"
        assert isinstance(creds.password, SecretString)
        assert len(creds.data_server_endpoints) == 1
        assert creds.data_server_endpoints[0] is connection

    def test_model_validate_roundtrip(self):
        """Test that model_dump -> model_validate is a roundtrip."""
        connection = DataServerEndpoint(
            host="mysql.example.com", port=3307, kind=DataServerEndpointKind.MYSQL
        )

        original = DataServerDetails(
            username="testuser",
            password="secret123",  # type: ignore[arg-type]
            data_server_endpoints=[connection],
        )

        dumped = original.model_dump()
        restored = DataServerDetails.model_validate(dumped)

        assert restored.username == original.username
        assert isinstance(restored.password, SecretString)
        assert restored.password is not None
        assert original.password is not None
        assert restored.password_str == original.password_str
        assert len(restored.data_server_endpoints) == len(original.data_server_endpoints) == 1
        assert restored.data_server_endpoints[0].host == original.data_server_endpoints[0].host
        assert restored.data_server_endpoints[0].port == original.data_server_endpoints[0].port
        assert restored.data_server_endpoints[0].kind == original.data_server_endpoints[0].kind

        # Test updated_at roundtrip (datetime -> ISO string -> datetime)
        assert isinstance(restored.updated_at, datetime)
        assert restored.updated_at == original.updated_at

    def test_model_validate_parses_updated_at(self):
        """Test model_validate parses ISO datetime strings and handles datetime objects."""
        # Test ISO string parsing
        data_with_iso = {
            "username": "testuser",
            "password": "secret123",
            "data_server_connections": [
                {
                    "kind": "http",
                    "host": "api.example.com",
                    "port": 8080,
                }
            ],
            "updated_at": "2024-01-15T10:30:45",
        }

        creds1 = DataServerDetails.model_validate(data_with_iso)
        assert isinstance(creds1.updated_at, datetime)
        assert creds1.updated_at == datetime(2024, 1, 15, 10, 30, 45)

        # Test datetime object handling
        specific_time = datetime(2024, 1, 15, 10, 30, 45)
        data_with_datetime = data_with_iso.copy()
        data_with_datetime["updated_at"] = specific_time

        creds2 = DataServerDetails.model_validate(data_with_datetime)
        assert isinstance(creds2.updated_at, datetime)
        assert creds2.updated_at == specific_time
