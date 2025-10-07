from fastapi import APIRouter

from agent_platform.core.data_connections.data_sources import DataSources
from agent_platform.core.data_server.data_server import DataServerDetails
from agent_platform.server.data_server.data_source import (
    DataSourceDefinition,
    delete_data_source_from_data_server,
    initialize_data_source,
    list_data_sources_from_data_server,
)

router = APIRouter()


@router.post("/list")
async def list_data_sources(data_server: DataServerDetails) -> list[DataSourceDefinition]:
    """Get all data sources created by the agent-server."""
    return await list_data_sources_from_data_server(data_server)


@router.post("/update", status_code=201)
async def upsert_data_source(payload: DataSources):
    """Creates the data sources on the given data server."""
    await initialize_data_source(payload)


@router.delete("/{data_source_name}", status_code=204)
async def delete_data_source(data_source_name: str, data_server: DataServerDetails):
    """Delete a data source."""
    await delete_data_source_from_data_server(data_source_name, data_server)
