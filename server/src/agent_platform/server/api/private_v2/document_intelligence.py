from fastapi import APIRouter, Depends
from sema4ai.data import DataSource
from sema4ai_docint.models import initialize_database
from sema4ai_docint.models.constants import DATA_SOURCE_NAME
from structlog import get_logger
from structlog.stdlib import BoundLogger

from agent_platform.core.document_intelligence.dataserver import DIDSConnectionDetails
from agent_platform.core.errors.base import PlatformError, PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode
from agent_platform.server.storage.postgres.postgres import PostgresConfig

logger: BoundLogger = get_logger(__name__)


def _require_document_intelligence_data_server():
    """Checks that a DIDS is configured for the agent server, or fail as a pre-ignition check."""
    # TODO: Implement the actual check
    raise PlatformHTTPError(
        ErrorCode.PRECONDITION_FAILED, "Document Intelligence Data Server is not configured"
    )


async def _build_datasource(connection_details: DIDSConnectionDetails):
    proper_json = connection_details.as_datasource_connection_input()

    try:
        DataSource.setup_connection_from_input_json(proper_json)

        # Drop existing database if it exists
        # Create admin datasource for administrative commands
        admin_ds = DataSource.model_validate(datasource_name="sema4ai")

        drop_sql = "DROP DATABASE IF EXISTS DocumentIntelligence;"
        admin_ds.execute_sql(drop_sql)

        create_sql = f'''
        CREATE DATABASE DocumentIntelligence
        WITH ENGINE = "postgres",
        PARAMETERS = {{
            "user": "{PostgresConfig.user}",
            "password": "{PostgresConfig.password}",
            "host": "{PostgresConfig.host}",
            "port": {PostgresConfig.port},
            "database": "{PostgresConfig.db}",
            "schema": "docint"
        }};
        '''

        admin_ds.execute_sql(create_sql)

        docint_ds = DataSource.model_validate(datasource_name=DATA_SOURCE_NAME)

        initialize_database("postgres", docint_ds)

    except Exception as e:
        raise PlatformError(
            ErrorCode.UNEXPECTED,
            f"Error initializing Document Intelligence database: Error: {e}",
        ) from e


router = APIRouter(dependencies=[Depends(_require_document_intelligence_data_server)])


@router.get("/ok")
async def ok():
    return {"ok": True}
