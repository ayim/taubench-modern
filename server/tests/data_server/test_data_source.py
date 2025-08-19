# pyright: reportMissingTypeStubs=false, reportMissingImports=false
from unittest.mock import patch

import pytest

from agent_platform.core.data_server.data_connection import (  # type: ignore[reportMissingTypeStubs, reportMissingImports]
    DataConnection,
    DataConnectionEngine,
)
from agent_platform.core.data_server.data_server import (  # type: ignore[reportMissingTypeStubs, reportMissingImports]
    DataServerDetails,
    DataServerEndpoint,
    DataServerEndpointKind,
)
from agent_platform.core.data_server.data_sources import (
    DataSources,  # type: ignore[reportMissingTypeStubs, reportMissingImports]
)
from agent_platform.core.utils import (
    SecretString,  # type: ignore[reportMissingTypeStubs, reportMissingImports]
)
from agent_platform.server.data_server.data_source import (
    initialize_data_source,  # type: ignore[reportMissingTypeStubs, reportMissingImports]
)


@pytest.mark.asyncio
async def test_initialize_data_source():
    # Arrange: build a realistic DataSources input
    endpoint = DataServerEndpoint(
        host="mysql.example.com",
        port=3306,
        kind=DataServerEndpointKind.MYSQL,
    )
    server_details = DataServerDetails(
        username="testuser",
        password=SecretString("secret123"),
        data_server_endpoints=[endpoint],
    )

    connection = DataConnection(
        id="conn-123",
        name="test_connection",
        engine=DataConnectionEngine.POSTGRES,
        configuration={
            "user": "postgres",
            "password": "pgsecret",
            "host": "postgres.example.com",
            "port": 5432,
            "database": "test_db",
        },
    )

    data_source_name = "my_datasource"
    data_sources = DataSources(
        data_server=server_details,
        data_sources={data_source_name: connection},
    )

    expected_connection_input = server_details.as_datasource_connection_input()

    with patch("agent_platform.server.data_server.data_source.DataSource") as mock_datasource_cls:
        admin_ds_mock = mock_datasource_cls.model_validate.return_value

        # Act
        await initialize_data_source(data_sources)

        # Assert: connection setup called with proper input
        mock_datasource_cls.setup_connection_from_input_json.assert_called_once_with(
            expected_connection_input
        )

        # Assert: admin datasource created for the known project
        mock_datasource_cls.model_validate.assert_called_once_with(datasource_name="sema4ai")

        # Assert: drop and create SQL executed
        calls = [c.args[0] for c in admin_ds_mock.execute_sql.call_args_list]
        assert any(call == f"DROP DATABASE IF EXISTS `{data_source_name}`;" for call in calls)

        # Check the CREATE DATABASE statement contains expected fragments
        assert any(
            (
                "CREATE DATABASE" in call
                and f"`{data_source_name}`" in call
                and f'ENGINE = "{connection.engine.value}"' in call
                and '"user": "postgres"' in call
                and '"password": "pgsecret"' in call
                and '"host": "postgres.example.com"' in call
                and '"port": 5432' in call
                and '"database": "test_db"' in call
            )
            for call in calls
        )

        # Exactly two SQL executions (DROP then CREATE) for one data source
        assert admin_ds_mock.execute_sql.call_count == 2
