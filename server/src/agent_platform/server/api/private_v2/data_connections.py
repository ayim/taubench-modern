import uuid

from fastapi import APIRouter, HTTPException, Request
from structlog import get_logger

from agent_platform.core.data_connections.data_connections import DataConnection as DbDataConnection
from agent_platform.core.payloads.data_connection import (
    DataConnection as DataConnectionPayload,
)
from agent_platform.core.payloads.data_connection import (
    DataConnectionsInspectRequest,
    DataConnectionsInspectResponse,
    DataConnectionTag,
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
    import datetime

    if data.id is not None:
        raise HTTPException(
            status_code=400,
            detail="Data connection ID must be None when creating a new data connection",
        )

    # Prevent users from setting the document_intelligence tag directly
    if DataConnectionTag.DOCUMENT_INTELLIGENCE in data.tags:
        raise HTTPException(
            status_code=400,
            detail=(
                f"The '{DataConnectionTag.DOCUMENT_INTELLIGENCE}' tag is managed exclusively "
                f"by the Document Intelligence configuration endpoint. "
                f"Please use the /api/v2/document-intelligence endpoint to configure "
                f"Document Intelligence data connections."
            ),
        )

    if data.created_at is None:
        data.created_at = datetime.datetime.now(datetime.UTC)

    if data.updated_at is None:
        data.updated_at = datetime.datetime.now(datetime.UTC)

    try:
        connection_id = str(uuid.uuid4())
        db_data_connection = DbDataConnection.from_payload(payload=data, connection_id=connection_id)
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
        raise HTTPException(status_code=500, detail=f"Failed to create data connection: {e!s}") from e


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
        raise HTTPException(status_code=500, detail=f"Failed to list data connections: {e!s}") from e


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
    # Prevent users from setting the document_intelligence tag directly
    if DataConnectionTag.DOCUMENT_INTELLIGENCE in data_connection.tags:
        raise HTTPException(
            status_code=400,
            detail=(
                f"The '{DataConnectionTag.DOCUMENT_INTELLIGENCE}' tag is managed exclusively "
                f"by the Document Intelligence configuration endpoint. "
                f"Please use the /api/v2/document-intelligence endpoint to configure "
                f"Document Intelligence data connections."
            ),
        )

    try:
        db_data_connection = DbDataConnection.from_payload(payload=data_connection, connection_id=connection_id)

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
        raise HTTPException(status_code=500, detail=f"Failed to update data connection: {e!s}") from e


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
        raise HTTPException(status_code=500, detail=f"Failed to delete data connection: {e!s}") from e


@router.post("/{connection_id}/inspect")
async def inspect_data_connection(
    connection_id: str,
    request: DataConnectionsInspectRequest,
    user: AuthedUser,
    storage: StorageDependency,
) -> DataConnectionsInspectResponse:
    """Inspect a data connection to get tables, columns and sample data."""
    try:
        # Get the data connection
        db_data_connection = await storage.get_data_connection(connection_id)

        # Import the inspection logic
        from agent_platform.server.kernel.data_connection_inspector import DataConnectionInspector

        inspector = DataConnectionInspector(db_data_connection, request)
        result = await inspector.inspect_connection()

        # Add inspection timestamp
        from datetime import UTC, datetime

        result.inspected_at = datetime.now(UTC).isoformat()

        logger.info(
            "Successfully inspected data connection",
            connection_id=connection_id,
            tables_found=len(result.tables),
            user_id=user.user_id,
        )

        return result
    except Exception as e:
        # Import error types inside the exception handler
        from agent_platform.core.errors.base import ErrorCode, PlatformHTTPError
        from agent_platform.server.kernel.data_connection_inspector import TableNotFoundError
        from agent_platform.server.kernel.ibis_utils import ConnectionFailedError

        logger.error(
            "Failed to inspect data connection",
            connection_id=connection_id,
            error=str(e),
            user_id=user.user_id,
        )

        # For ConnectionFailedError, expose message and details separately for UI expand/collapse
        if isinstance(e, ConnectionFailedError):
            error_data = {"details": e.details} if e.details else None
            raise PlatformHTTPError(
                ErrorCode.UNEXPECTED,
                e.message,  # Primary message (shortened)
                data=error_data,
            ) from e

        # For TableNotFoundError, also expose details separately
        if isinstance(e, TableNotFoundError):
            error_data = {"details": e.details} if e.details else None
            # Use a shortened message without the full details
            short_message = (
                f"Table '{e.table_name}' not found or not accessible. "
                "Please verify the table name and your permissions."
            )
            raise PlatformHTTPError(
                ErrorCode.UNEXPECTED,
                short_message,  # Primary message (shortened, user-friendly)
                data=error_data,
            ) from e

        # For other exceptions, include the generic prefix and full error as details
        original_error = str(e)
        # Try to get more context from the exception chain
        if e.__cause__:
            original_error = f"{original_error}\n\nCaused by: {e.__cause__!s}"
        error_data = {"details": original_error}
        raise PlatformHTTPError(
            ErrorCode.UNEXPECTED,
            f"Failed to inspect data connection: {e!s}",
            data=error_data,
        ) from e


@router.post("/inspect-file-as-data-connection")
async def inspect_file_as_data_connection(
    request: Request,
    user: AuthedUser,
) -> DataConnectionsInspectResponse:
    """Inspect a file to get tables, columns and sample data as if it were a data connection."""

    from agent_platform.core.errors.base import PlatformError, PlatformHTTPError
    from agent_platform.core.errors.responses import ErrorCode

    try:
        # Get the file name from headers
        file_name = request.headers.get("X-File-Name")
        if not file_name:
            raise PlatformError(error_code=ErrorCode.BAD_REQUEST, message="X-File-Name header is required")

        # Get the file contents from the request body
        file_contents = await request.body()

        # Import the data reader functionality
        from agent_platform.server.data_frames.data_reader import (
            create_file_data_reader_from_contents,
        )
        from agent_platform.server.file_manager.utils import guess_mimetype

        # Determine MIME type from file extension and/or content
        mime_type = guess_mimetype(file_name, file_contents)

        # Create a file data reader from the contents
        data_reader = create_file_data_reader_from_contents(
            file_contents=file_contents,
            file_name=file_name,
            mime_type=mime_type,
        )

        # Convert the data reader sheets to TableInfo objects
        from agent_platform.server.data_frames.file_inspection_utils import create_table_info

        tables = []
        has_multiple_sheets = data_reader.has_multiple_sheets()
        for sheet in data_reader.iter_sheets():
            table_info = create_table_info(sheet, file_name, has_multiple_sheets)
            tables.append(table_info)

        # Add inspection timestamp
        from datetime import UTC, datetime

        logger.info(
            "Successfully inspected file as data connection",
            file_name=file_name,
            tables_found=len(tables),
        )

        return DataConnectionsInspectResponse(
            tables=tables,
            inspected_at=datetime.now(UTC).isoformat(),
        )

    except PlatformHTTPError:
        raise
    except Exception as e:
        logger.error(
            "Failed to inspect file as data connection",
            file_name=request.headers.get("X-File-Name", "Not received"),
            error=e,
        )
        raise PlatformHTTPError(
            error_code=ErrorCode.UNEXPECTED,
            message=f"Failed to inspect file as data connection: {e!s}",
        ) from e
