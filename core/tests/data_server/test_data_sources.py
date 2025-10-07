from sema4ai_docint.models.constants import DATA_SOURCE_NAME

from agent_platform.core.data_connections.data_sources import DataSources
from agent_platform.core.data_server.data_server import (
    DataServerEndpointKind,
)
from agent_platform.core.payloads.data_connection import PostgresDataConnectionConfiguration
from agent_platform.core.utils import SecretString


class TestDataSources:
    def test_serialization(self):
        data = {
            "data_server": {
                "username": "testuser",
                "password": "secret123",
                "data_server_endpoints": [
                    {
                        "kind": "mysql",
                        "host": "mysql.example.com",
                        "port": 3307,
                    }
                ],
            },
            "data_sources": {
                DATA_SOURCE_NAME: {
                    "id": "123",
                    "name": "test_connection",
                    "description": "Test connection",
                    "engine": "postgres",
                    "configuration": {
                        "user": "postgres",
                        "password": "secret123",
                        "host": "postgres.example.com",
                        "port": 5432,
                        "database": "test_db",
                        "schema": "public",
                        "sslmode": None,
                    },
                    "tags": [],
                }
            },
        }

        sources = DataSources.model_validate(data)

        assert sources.data_server.username == "testuser"
        assert isinstance(sources.data_server.password, SecretString)
        assert sources.data_server.password is not None
        assert sources.data_server.password.get_secret_value() == "secret123"
        assert len(sources.data_server.data_server_endpoints) == 1
        assert sources.data_server.data_server_endpoints[0].host == "mysql.example.com"
        assert sources.data_server.data_server_endpoints[0].port == 3307
        assert sources.data_server.data_server_endpoints[0].kind == DataServerEndpointKind.MYSQL

        assert len(sources.data_sources) == 1
        assert sources.data_sources[DATA_SOURCE_NAME].id == "123"
        assert sources.data_sources[DATA_SOURCE_NAME].name == "test_connection"
        assert sources.data_sources[DATA_SOURCE_NAME].description == "Test connection"
        assert sources.data_sources[DATA_SOURCE_NAME].engine == "postgres"
        config = sources.data_sources[DATA_SOURCE_NAME].configuration
        assert isinstance(config, PostgresDataConnectionConfiguration)
        assert config.user == "postgres"
        assert config.password == "secret123"
        assert config.host == "postgres.example.com"
        assert config.port == 5432
        assert config.database == "test_db"

        actual = sources.model_dump(mode="json")
        assert "updated_at" in actual["data_server"], "updated_at should be automatically set"

        # remove updated_at so the comparison succeeds
        actual["data_server"].pop("updated_at")
        assert actual == data
