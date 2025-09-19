import uuid

from fastapi import APIRouter, HTTPException
from structlog import get_logger

from agent_platform.core.data_connections.data_connections import (
    DataConnection as DbDataConnection,
)
from agent_platform.core.payloads.data_connection import (
    DataConnection as DataConnectionPayload,
)
from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.auth import AuthedUser

router = APIRouter()
logger = get_logger(__name__)


@router.post("/", response_model=DataConnectionPayload)
async def create_data_connection(
    data: DataConnectionPayload,
    user: AuthedUser,
    storage: StorageDependency,
) -> DataConnectionPayload:
    """Create a new data connection."""
    if data.id is not None:
        raise HTTPException(
            status_code=400,
            detail="Data connection ID must be None when creating a new data connection",
        )
    try:
        connection_id = str(uuid.uuid4())
        db_data_connection = DbDataConnection.from_payload(
            payload=data, connection_id=connection_id
        )
        await storage.set_data_connection(db_data_connection)

        logger.info(
            "Created data connection",
            connection_id=connection_id,
            connection_name=data.name,
            engine=data.engine,
            user_id=user.user_id,
        )

        created_db_data_connection = await storage.get_data_connection(connection_id)
        return created_db_data_connection.to_payload()

    except Exception as e:
        logger.error(
            "Failed to create data connection",
            error=str(e),
            connection_name=data.name,
            engine=data.engine,
            user_id=user.user_id,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to create data connection: {e!s}"
        ) from e


@router.get("/", response_model=list[DataConnectionPayload])
async def list_data_connections(
    user: AuthedUser,
    storage: StorageDependency,
) -> list[DataConnectionPayload]:
    """List all data connections for the authenticated user."""
    try:
        db_data_connections = await storage.get_data_connections()

        payload_connections = []
        for conn in db_data_connections:
            payload_connection = conn.to_payload()
            payload_connections.append(payload_connection)

        return payload_connections

    except Exception as e:
        logger.error("Failed to list data connections", error=str(e), user_id=user.user_id)
        raise HTTPException(
            status_code=500, detail=f"Failed to list data connections: {e!s}"
        ) from e


@router.get("/{connection_id}", response_model=DataConnectionPayload)
async def get_data_connection(
    connection_id: str,
    user: AuthedUser,
    storage: StorageDependency,
) -> DataConnectionPayload:
    """Get a specific data connection by ID."""
    try:
        db_data_connection = await storage.get_data_connection(connection_id)
        return db_data_connection.to_payload()

    except Exception as e:
        logger.error(
            "Failed to get data connection",
            connection_id=connection_id,
            error=str(e),
            user_id=user.user_id,
        )
        raise HTTPException(status_code=500, detail=f"Failed to get data connection: {e!s}") from e


@router.put("/{connection_id}", response_model=DataConnectionPayload)
async def update_data_connection(
    connection_id: str,
    data_connection: DataConnectionPayload,
    user: AuthedUser,
    storage: StorageDependency,
) -> DataConnectionPayload:
    """Update an existing data connection."""
    try:
        db_data_connection = DbDataConnection.from_payload(
            payload=data_connection, connection_id=connection_id
        )

        await storage.update_data_connection(db_data_connection)

        updated_db_data_connection = await storage.get_data_connection(connection_id)
        return updated_db_data_connection.to_payload()

    except Exception as e:
        logger.error(
            "Failed to update data connection",
            connection_id=connection_id,
            error=str(e),
            connection_name=data_connection.name,
            engine=data_connection.engine,
            user_id=user.user_id,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to update data connection: {e!s}"
        ) from e


@router.delete("/{connection_id}", response_model=None)
async def delete_data_connection(
    connection_id: str,
    user: AuthedUser,
    storage: StorageDependency,
) -> None:
    """Delete a data connection."""
    try:
        await storage.delete_data_connection(connection_id)
    except Exception as e:
        logger.error(
            "Failed to delete data connection",
            connection_id=connection_id,
            error=str(e),
            user_id=user.user_id,
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to delete data connection: {e!s}"
        ) from e
