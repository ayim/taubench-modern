from sema4ai.data import DataSource

from agent_platform.core.data_server.data_sources import DataSources


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
        WITH ENGINE = "{connection.engine.value}",
        PARAMETERS = {{
            {connection.build_mindsdb_parameters()}
        }};
        '''

        admin_ds.execute_sql(create_sql)
