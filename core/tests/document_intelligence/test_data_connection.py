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
            "id": "123",
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

        assert connection.id == "123"
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
            "id": "123",
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

    def test_invalid_engine(self):
        """Test that model_validate errors on an invalid engine"""
        data = {
            "id": "123",
            "name": "test",
            "engine": "sqlite",
            "configuration": {
                "path": "/tmp/sqlite.db",
            },
        }

        with pytest.raises(PlatformHTTPError) as exc_info:
            DataConnection.model_validate(data)

        assert exc_info.value.status_code == 400
        assert "sqlite" in exc_info.value.detail
