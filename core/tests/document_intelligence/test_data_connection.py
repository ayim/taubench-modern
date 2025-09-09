import pytest

from agent_platform.core.data_server.data_connection import (
    DataConnection,
    DataConnectionEngine,
)
from agent_platform.core.errors.base import PlatformHTTPError


class TestDataConnection:
    """Test DataConnection dataclass functionality."""

    def test_postgres_connection(self):
        """Test that model_validate works for Postgres data connections."""
        data = {
            "external_id": "123",
            "name": "test",
            "engine": "postgres",
            "configuration": {
                "user": "user",
                "password": "pass",
                "host": "localhost",
                "port": 5432,
                "database": "test",
            },
        }

        connection = DataConnection.model_validate(data)

        assert connection.external_id == "123"
        assert connection.name == "test"
        assert connection.engine == DataConnectionEngine.POSTGRES
        assert connection.configuration == data["configuration"]

        # mode=python should give us the original information
        dump = connection.model_dump(mode="python")
        assert dump == data

        # mode=json should redact the password
        dump = connection.model_dump(mode="json")
        expected = data.copy()
        expected["configuration"]["password"] = "<REDACTED>"
        assert dump == expected

    def test_missing_connection_details(self):
        """Test that model_validate identifies missing, required attributes"""
        data = {
            "external_id": "123",
            "name": "test",
            "engine": "postgres",
            "configuration": {
                "user": "user",
                "password": "pass",
                # Missing host
                "port": 5432,
                "database": "test",
            },
        }

        with pytest.raises(PlatformHTTPError) as exc_info:
            DataConnection.model_validate(data)

        assert exc_info.value.status_code == 400
        assert "host" in exc_info.value.detail

    def test_unknown_engine(self):
        """Test that a unknown engine is allowed through with no validation logic"""
        data = {
            "external_id": "123",
            "name": "test",
            "engine": "sqlite",
            "configuration": {
                "path": "/tmp/sqlite.db",
            },
        }

        conn = DataConnection.model_validate(data)

        assert conn.external_id == "123"
        assert conn.name == "test"
        assert conn.engine == "sqlite"
        assert conn.configuration == data["configuration"]
        assert '"path": "/tmp/sqlite.db"' in conn.build_mindsdb_parameters()

    def test_mysql_engine(self):
        """Test that a MySQL engine is allowed through with no validation logic"""
        data = {
            "external_id": "123",
            "name": "test",
            "engine": "mysql",
            "configuration": {
                "user": "user",
                "password": "pass",
                "host": "localhost",
                "port": 3306,
                "database": "test",
            },
        }

        conn = DataConnection.model_validate(data)

        assert conn.external_id == "123"
        assert conn.name == "test"
        assert conn.engine == "mysql"
        assert conn.configuration == data["configuration"]
        assert '"user": "user"' in conn.build_mindsdb_parameters()
        assert '"password": "pass"' in conn.build_mindsdb_parameters()
        assert '"host": "localhost"' in conn.build_mindsdb_parameters()
        assert '"port": 3306' in conn.build_mindsdb_parameters()
        assert '"database": "test"' in conn.build_mindsdb_parameters()

    def test_id_fallback_for_external_id(self):
        """Test that id field is used as fallback when external_id is missing."""
        data = {
            "id": "fallback-123",  # Using deprecated id field
            "name": "fallback_test",
            "engine": "postgres",
            "configuration": {
                "user": "user",
                "password": "pass",
                "host": "localhost",
                "port": 5432,
                "database": "test",
            },
        }

        conn = DataConnection.model_validate(data)
        assert conn.external_id == "fallback-123"  # Should use id as fallback
        assert conn.id is None  # Original id should be discarded after fallback
        assert conn.name == "fallback_test"

    def test_id_fallback_when_external_id_is_none(self):
        """Test that id field is used as fallback when external_id is None."""
        data = {
            "external_id": None,
            "id": "fallback-456",  # Using deprecated id field
            "name": "fallback_test2",
            "engine": "postgres",
            "configuration": {
                "user": "user",
                "password": "pass",
                "host": "localhost",
                "port": 5432,
                "database": "test",
            },
        }

        conn = DataConnection.model_validate(data)
        assert conn.external_id == "fallback-456"  # Should use id as fallback
        assert conn.id is None  # Original id should be discarded after fallback
        assert conn.name == "fallback_test2"
