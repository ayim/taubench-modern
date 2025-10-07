import json
from dataclasses import dataclass
from typing import Any

from sema4ai.data import DataSource

from agent_platform.core.data_connections.data_sources import DataSources
from agent_platform.core.data_server.data_server import DataServerDetails

_database_to_ignore = ["files"]


@dataclass
class DataSourceDefinition:
    name: str
    type: str
    engine: str | None
    connection_data: dict[str, Any] | None

    def model_dump(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "engine": self.engine,
            "connection_data": self.connection_data,
        }

    @classmethod
    def model_validate(cls, data: dict[str, Any]) -> "DataSourceDefinition":
        def get_value(key: str) -> Any:
            return data.get(key) or data.get(key.upper())

        connection_data_str = get_value("connection_data")
        if connection_data_str:
            connection_data = json.loads(connection_data_str)
        else:
            connection_data = None

        return cls(
            name=get_value("name"),
            type=get_value("type"),
            engine=get_value("engine"),
            connection_data=connection_data,
        )


async def initialize_data_source(data_sources: DataSources):
    """
    Given the details of a Data Server, create the data sources on the Data Server.

    This function is idempotent. It will drop the data source if it already exists
    and then create it.
    """
    proper_json = data_sources.data_server.as_datasource_connection_input()

    DataSource.setup_connection_from_input_json(proper_json)

    # Create admin datasource for administrative commands. We assume this project always exists
    # by virtue of data-server-cli setup.
    admin_ds = DataSource.model_validate(datasource_name="sema4ai")

    # Create each data source, with a DROP DATABASE IF EXISTS to ensure we don't have any
    # leftovers from previous runs.
    for data_source_name, connection in data_sources.data_sources.items():
        drop_sql = f"DROP DATABASE IF EXISTS `{data_source_name}`;"
        admin_ds.execute_sql(drop_sql)

        # Pass the data connection details directly to the datasource
        create_sql = f'''
        CREATE DATABASE `{data_source_name}`
        WITH ENGINE = "{connection.engine}",
        PARAMETERS = {{
            {connection.build_mindsdb_parameters()}
        }};
        '''

        admin_ds.execute_sql(create_sql)


async def list_data_sources_from_data_server(
    data_server: DataServerDetails,
) -> list[DataSourceDefinition]:
    """
    List the data sources on the Data Server.
    """
    data_server_json = data_server.as_datasource_connection_input()
    DataSource.setup_connection_from_input_json(data_server_json)

    data_source = DataSource.model_validate(datasource_name="sema4ai")

    results = data_source.execute_sql(
        """
        SELECT NAME, TYPE, ENGINE, CONNECTION_DATA
        FROM INFORMATION_SCHEMA.DATABASES WHERE TYPE = 'data'
        """
    )
    if results:
        return [
            DataSourceDefinition.model_validate(row)
            for row in results.iter_as_dicts()
            if row["NAME"] not in _database_to_ignore
        ]

    return []


async def delete_data_source_from_data_server(
    data_source_name: str, data_server: DataServerDetails
):
    """
    Delete a data source from the Data Server.
    """
    data_server_json = data_server.as_datasource_connection_input()
    DataSource.setup_connection_from_input_json(data_server_json)

    data_source = DataSource.model_validate(datasource_name="sema4ai")
    data_source.execute_sql(f"DROP DATABASE IF EXISTS `{data_source_name}`")
