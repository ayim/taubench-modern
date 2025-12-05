from collections.abc import AsyncGenerator
from enum import StrEnum
from typing import Annotated, Any, cast

import structlog
from fastapi import Depends, Request, UploadFile
from sema4ai.data import DataSource
from sema4ai.data._data_source import ConnectionNotSetupError
from sema4ai_docint import DIService, build_di_service
from sema4ai_docint.agent_server_client import AgentServerClient
from sema4ai_docint.agent_server_client.transport import MemoryTransport
from sema4ai_docint.extraction.reducto.async_ import AsyncExtractionClient
from starlette.concurrency import run_in_threadpool

from agent_platform.core.agent.agent import Agent
from agent_platform.core.configurations.quotas import QuotasService
from agent_platform.core.data_server.data_server import DataServerDetails
from agent_platform.core.errors import ErrorCode
from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.errors.quotas import (
    AgentQuotaExceededError,
    MCPServerQuotaExceededError,
)
from agent_platform.core.errors.work_items import (
    WorkItemFileAttachmentTooLargeError,
    WorkItemPayloadTooLargeError,
)
from agent_platform.core.integrations.settings.reducto import ReductoSettings
from agent_platform.server.auth import AuthedUser
from agent_platform.server.document_intelligence import DocumentIntelligenceService
from agent_platform.server.file_manager import BaseFileManager, FileManagerService
from agent_platform.server.secret_manager.base import BaseSecretManager
from agent_platform.server.secret_manager.option import SecretService
from agent_platform.server.storage import BaseStorage, StorageService
from agent_platform.server.storage.errors import (
    DIDSConnectionDetailsNotFoundError,
    IntegrationNotFoundError,
)

StorageDependency = Annotated[BaseStorage, Depends(StorageService.get_instance)]

SecretDependency = Annotated[BaseSecretManager, Depends(SecretService.get_instance)]

logger = structlog.get_logger(__name__)


def get_file_manager(storage: StorageDependency) -> BaseFileManager:
    """FastAPI dependency to provide the file manager service.

    This dependency explicitly depends on the storage dependency to ensure
    proper initialization order.

    Args:
        storage: The storage service instance (automatically injected).

    Returns:
        The file manager service instance.
    """
    return FileManagerService.get_instance(storage)


FileManagerDependency = Annotated[BaseFileManager, Depends(get_file_manager)]


async def check_agent_quota(storage: StorageDependency) -> None:
    """FastAPI dependency to check if agent creation is within quota limits.

    Raises AgentQuotaExceededError if the maximum number of agents
    has been reached.

    Args:
        storage: The storage service instance (automatically injected).

    Raises:
        AgentQuotaExceededError: If the agent quota limit has been reached.
    """
    quotas_service = await QuotasService.get_instance()
    max_agents = quotas_service.get_max_agents()
    current_count = await storage.count_agents()

    if current_count >= max_agents:
        raise AgentQuotaExceededError(
            current_count=current_count,
            quota_limit=max_agents,
        )


AgentQuotaCheck = Annotated[None, Depends(check_agent_quota)]


async def check_mcp_server_quota(storage: StorageDependency) -> None:
    """FastAPI dependency to check if MCP server creation is within quota limits.

    Raises HTTPException with 429 status if the maximum number of MCP servers
    has been reached.

    Args:
        storage: The storage service instance (automatically injected).

    Raises:
        HTTPException: If the MCP server quota limit has been reached.
    """
    quotas_service = await QuotasService.get_instance()
    max_mcp_servers = quotas_service.get_max_mcp_servers_in_agent()
    current_count = await storage.count_mcp_servers()

    if current_count >= max_mcp_servers:
        raise MCPServerQuotaExceededError(
            current_count=current_count,
            quota_limit=max_mcp_servers,
        )


MCPQuotaCheck = Annotated[None, Depends(check_mcp_server_quota)]


async def check_work_item_payload_size(request: Request) -> None:
    """FastAPI dependency to check work item payload size against quota limits.

    Raises WorkItemPayloadTooLargeError if the payload exceeds the configured limit.

    Args:
        request: The FastAPI request object containing the payload.

    Raises:
        WorkItemPayloadTooLargeError: If the payload size exceeds the quota limit.
    """
    # Get the raw body bytes and calculate size in KB
    body_bytes = await request.body()
    size_bytes = len(body_bytes)
    size_kb = size_bytes / 1024

    # Get the quota limit from QuotasService
    quotas_service = await QuotasService.get_instance()
    max_payload_size_kb = quotas_service.get_max_work_item_payload_size()

    # Check if payload exceeds the limit
    if size_kb > max_payload_size_kb:
        raise WorkItemPayloadTooLargeError(
            payload_size=int(size_kb), allowed_payload_size=max_payload_size_kb
        )


WorkItemPayloadSizeCheck = Annotated[None, Depends(check_work_item_payload_size)]


async def check_platform_params_validity(request: Request, storage: StorageDependency) -> None:
    """FastAPI dependency to validate platform_params_ids in agent requests.

    Parses the request body and validates that all platform_params_ids exist
    in the database before the endpoint processes the request.

    Args:
        request: The FastAPI request object containing the payload.
        storage: The storage service instance (automatically injected).

    Raises:
        PlatformHTTPError: If any platform_params_ids are invalid.
    """
    import json

    from agent_platform.core.errors import ErrorCode
    from agent_platform.core.errors.base import PlatformHTTPError

    try:
        # Read and parse the request body
        body = await request.body()
        if not body:
            return

        payload_dict = json.loads(body)
        platform_params_ids = payload_dict.get("platform_params_ids", [])

        if not platform_params_ids:
            return

        # Validate each platform_params_id
        invalid_ids = []
        for platform_params_id in platform_params_ids:
            try:
                await storage.get_platform_params(platform_params_id)
            except Exception:
                invalid_ids.append(platform_params_id)

        if invalid_ids:
            raise PlatformHTTPError(
                error_code=ErrorCode.BAD_REQUEST,
                message=f"Invalid platform_params_ids: {invalid_ids}",
                data={"invalid_platform_params_ids": invalid_ids},
            )

    except json.JSONDecodeError:
        # If we can't parse JSON, let FastAPI handle the validation
        pass


PlatformParamsValidationCheck = Annotated[None, Depends(check_platform_params_validity)]


async def check_work_item_file_attachment_size(file: UploadFile | str) -> None:
    # We have file directly uploaded to the POST, we validate that case only
    if not isinstance(file, str):
        # Handle case where file.size might be None
        if file.size is None:
            return  # Skip validation if size is unknown

        file_size_mb = round(file.size / (1024 * 1024), 5)  # bytes to mb, 5 decimal places
        quotas_service = await QuotasService.get_instance()
        max_work_item_file_size = float(quotas_service.get_max_work_item_file_attachment_size())

        # Check if file attachment size exceeds the allowed limit
        if file_size_mb > max_work_item_file_size:
            raise WorkItemFileAttachmentTooLargeError(
                payload_size=file_size_mb, allowed_payload_size=max_work_item_file_size
            )


WorkItemFileAttachmentSizeCheck = Annotated[None, Depends(check_work_item_file_attachment_size)]


# -----------------------------------------------------------------------------
# Document Intelligence dependencies
# -----------------------------------------------------------------------------


async def get_dids_connection_details(storage: StorageDependency) -> DataServerDetails:
    """Fetch and return validated DIDS connection details.

    This wraps storage access to enable composition in other dependencies and
    keeps the validation in the API layer.
    """
    # Use new integration table instead of old dids_connection_details table
    try:
        data_server_integration = await storage.get_integration_by_kind("data_server")

        # Convert Integration settings to DataServerDetails format
        settings_dict = data_server_integration.settings.model_dump()
        details = DataServerDetails.model_validate(settings_dict)
    except IntegrationNotFoundError as e:
        raise DIDSConnectionDetailsNotFoundError(
            "Document Intelligence Data Server connection details not found"
        ) from e

    # Inline validation mirroring _require_document_intelligence_data_server
    if not details.username or not details.username.strip():
        raise DIDSConnectionDetailsNotFoundError(
            "Document Intelligence Data Server configuration is missing username"
        )

    if not details.password_str or not details.password_str.strip():
        raise DIDSConnectionDetailsNotFoundError(
            "Document Intelligence Data Server configuration is missing password"
        )

    if not details.data_server_endpoints:
        raise DIDSConnectionDetailsNotFoundError(
            "Document Intelligence Data Server configuration is missing connections"
        )

    for idx, conn in enumerate(details.data_server_endpoints):
        if not getattr(conn, "host", None) or not str(conn.host).strip():
            raise DIDSConnectionDetailsNotFoundError(
                f"Document Intelligence Data Server connection #{idx} is missing host"
            )
        if not getattr(conn, "port", None) or int(conn.port) <= 0:
            raise DIDSConnectionDetailsNotFoundError(
                f"Document Intelligence Data Server connection #{idx} has invalid port"
            )

    return details


DIDSDetailsDependency = Annotated[DataServerDetails, Depends(get_dids_connection_details)]


def get_docint_datasource(details: DIDSDetailsDependency) -> DataSource:
    """Ensure datasource setup for current configuration, then return it.

    Note: Uses a singleton service, mirroring other option services to avoid
    unsafe global caching patterns.
    """
    service = DocumentIntelligenceService.get_instance(details)
    datasource = service.get_docint_datasource()

    # Lightweight connectivity check: verify actual network connectivity
    try:
        datasource.connection()._http_connection.login()
    except ConnectionNotSetupError as e:
        raise PlatformHTTPError(
            ErrorCode.PRECONDITION_FAILED,
            "Document Intelligence datasource connection not properly configured.",
        ) from e
    except Exception as e:
        raise PlatformHTTPError(
            ErrorCode.PRECONDITION_FAILED,
            f"Failed to login to Document Intelligence data source: {e!s}",
        ) from e

    return datasource


DocIntDatasourceDependency = Annotated[DataSource, Depends(get_docint_datasource)]


async def get_agent_server_transport(
    request: Request, agent_id: str | None = None, thread_id: str | None = None
) -> MemoryTransport:
    """Get an agent server transport from the sema4ai-docint package for use in DIv2.

    Args:
        agent_id: The agent ID to attach to the transport instance as context
        thread_id: The thread ID to attach to the transport instance as context, this is
            required for transport file operations.
    """
    # Get the authorization header if it exists so it can be added to the transport
    additional_headers = None
    if "Authorization" in request.headers:
        additional_headers = {"Authorization": request.headers["Authorization"]}

    return MemoryTransport(
        base_url=str(request.base_url),
        base_path="",
        agent_id=agent_id,
        thread_id=thread_id,
        app=request.app,
        additional_headers=additional_headers,
    )


AgentServerTransportDependency = Annotated[MemoryTransport, Depends(get_agent_server_transport)]


async def get_agent_server_client(transport: AgentServerTransportDependency) -> AgentServerClient:
    """Get an agent server client from the sema4ai-docint package for use in DIv2.

    Ensures the file management client points to this server instance by
    deriving the base URL from the current request and setting
    SEMA4AI_FILE_MANAGEMENT_URL if it is not already set.
    """
    # Create client off-thread since it performs sync I/O (health check)
    client = await run_in_threadpool(AgentServerClient, transport=transport)
    return client


AgentServerClientDependency = Annotated[AgentServerClient, Depends(get_agent_server_client)]


async def get_async_extraction_client(
    storage: StorageDependency,
) -> AsyncGenerator[AsyncExtractionClient, Any]:
    """Get an async extraction client from the sema4ai-docint package for use in DIv2."""
    # TODO: Consider performance gains from switching this depedency to use a singleton
    # service pattern like storage. In such a scenario, we would want to pay attention
    # to changes in the reducto integration configuration.
    reducto_integration = await storage.get_integration_by_kind("reducto")
    reducto_settings = reducto_integration.settings
    if not isinstance(reducto_settings, ReductoSettings):
        raise ValueError("Expected ReductoSettings for reducto integration")

    reducto_settings = cast(ReductoSettings, reducto_settings)

    # Convert SecretString to str if needed
    from agent_platform.core.utils import SecretString

    api_key = (
        reducto_settings.api_key.get_secret_value()
        if isinstance(reducto_settings.api_key, SecretString)
        else reducto_settings.api_key
    )

    async with AsyncExtractionClient(
        api_key,
        disable_ssl_verification=False,
        base_url=reducto_settings.endpoint,
    ) as client:
        yield client


AsyncExtractionClientDependency = Annotated[
    AsyncExtractionClient, Depends(get_async_extraction_client)
]


async def _reducto_api_key(storage: StorageDependency) -> str:
    reducto_integ = await storage.get_integration_by_kind("reducto")
    reducto_settings = reducto_integ.settings
    if not isinstance(reducto_settings, ReductoSettings):
        raise ValueError("Expected ReductoSettings for reducto integration")

    reducto_settings = cast(ReductoSettings, reducto_settings)

    from agent_platform.core.utils import SecretString

    if isinstance(reducto_settings.api_key, SecretString):
        return reducto_settings.api_key.get_secret_value()
    else:
        return str(reducto_settings.api_key)


async def get_di_service(
    datasource: DocIntDatasourceDependency,
    storage: StorageDependency,
    transport: AgentServerTransportDependency,
) -> "DIService":
    api_key = await _reducto_api_key(storage)

    return build_di_service(
        datasource=datasource,
        sema4_api_key=api_key,
        agent_server_transport=transport,
    )


DIDependency = Annotated["DIService", Depends(get_di_service)]


# Constant from agent-spec
AGENT_PERSISTENCE_MODE_KEY = "di-persistence"


class PersistenceMode(StrEnum):
    """
    The persistence mode of the document intelligence service.
    """

    FILE = "file"
    DATABASE = "database"


def _is_docint_rag_agent(agent: Agent) -> bool:
    """
    Returns True if the agent has one of the "canonical" Document Intelligence action packages
    that have historically required a Postgres database.
    """
    return any(
        ap.name in ("Document Intelligence", "Document Insights") for ap in agent.action_packages
    )


async def _persistence_mode(agent: Agent) -> PersistenceMode:
    """
    Get the persistence mode of the document intelligence service.
    """
    if _is_docint_rag_agent(agent):
        return PersistenceMode.DATABASE

    if not agent.extra:
        return PersistenceMode.FILE
    persistence_mode_val = agent.agent_settings().get(AGENT_PERSISTENCE_MODE_KEY, "file")
    try:
        return PersistenceMode(persistence_mode_val)
    except ValueError:
        logger.warning(
            "Invalid persistence mode {persistence_mode_val} for agent {agent.id}",
            persistence_mode_val=persistence_mode_val,
            agent_id=agent.agent_id,
        )
        return PersistenceMode.FILE


async def di_service_with_persistence(
    user: AuthedUser,
    agent_id: str,
    thread_id: str,
    storage: StorageDependency,
    transport: AgentServerTransportDependency,
) -> "DIService":
    """Construct the DIService API client introspecting the current Agent."""
    # Verify thread
    thread = await storage.get_thread(user.user_id, thread_id)
    if not thread:
        raise PlatformHTTPError(
            error_code=ErrorCode.NOT_FOUND,
            message=f"Thread {thread_id} not found",
        )

    # Verify agent
    agent = await storage.get_agent(user.user_id, agent_id)
    if not agent:
        raise PlatformHTTPError(
            error_code=ErrorCode.NOT_FOUND,
            message=f"Agent {agent_id} not found",
        )

    # TODO we haven't implemented the DATABASE persistence mode yet.
    # Hard-code it to always be FILE.
    # persistence_mode = await _persistence_mode(agent)
    persistence_mode = PersistenceMode.FILE

    if persistence_mode == PersistenceMode.DATABASE:
        # Fall back to "classic" Document Intelligence service with a required Postgres datasource
        # Manually resolve the datasource dependency only when needed
        details = await get_dids_connection_details(storage)
        datasource = get_docint_datasource(details)
        return await get_di_service(datasource, storage, transport)
    elif persistence_mode == PersistenceMode.FILE:
        from sema4ai_docint.services.persistence import ChatFilePersistenceService
        from sema4ai_docint.services.persistence.file import AgentServerChatFileAccessor

        api_key = await _reducto_api_key(storage)

        # Use agent server's REST API to interact with chat files for caching.
        # This is mutually exclusive with a Datasource (postgres database).
        return build_di_service(
            datasource=None,
            sema4_api_key=api_key,
            agent_server_transport=transport,
            persistence_service=ChatFilePersistenceService(
                chat_file_accessor=AgentServerChatFileAccessor(thread_id, transport),
            ),
        )

    raise Exception(f"Unhandled persistence mode {persistence_mode} for agent {agent.agent_id}")


CachingDIServiceDependency = Annotated["DIService", Depends(di_service_with_persistence)]
