"""FastAPI dependencies used for injection."""

from typing import Annotated

from fastapi import Depends, Request, UploadFile
from sema4ai.data import DataSource

from agent_platform.core.configurations.quotas import QuotasService
from agent_platform.core.document_intelligence.dataserver import DIDSConnectionDetails
from agent_platform.core.errors.quotas import (
    AgentQuotaExceededError,
    MCPServerQuotaExceededError,
)
from agent_platform.core.errors.work_items import (
    WorkItemFileAttachmentTooLargeError,
    WorkItemPayloadTooLargeError,
)
from agent_platform.server.document_intelligence import DocumentIntelligenceService
from agent_platform.server.file_manager import BaseFileManager, FileManagerService
from agent_platform.server.secret_manager.base import BaseSecretManager
from agent_platform.server.secret_manager.option import SecretService
from agent_platform.server.storage import BaseStorage, StorageService
from agent_platform.server.storage.errors import DIDSConnectionDetailsNotFoundError

StorageDependency = Annotated[BaseStorage, Depends(StorageService.get_instance)]

SecretDependency = Annotated[BaseSecretManager, Depends(SecretService.get_instance)]


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


async def get_dids_connection_details(storage: StorageDependency) -> DIDSConnectionDetails:
    """Fetch and return validated DIDS connection details.

    This wraps storage access to enable composition in other dependencies and
    keeps the validation in the API layer.
    """
    details = await storage.get_dids_connection_details()

    # Inline validation mirroring _require_document_intelligence_data_server
    if not details.username or not details.username.strip():
        raise DIDSConnectionDetailsNotFoundError(
            "Document Intelligence Data Server configuration is missing username"
        )

    if not details.password or not details.password.get_secret_value().strip():
        raise DIDSConnectionDetailsNotFoundError(
            "Document Intelligence Data Server configuration is missing password"
        )

    if not details.connections:
        raise DIDSConnectionDetailsNotFoundError(
            "Document Intelligence Data Server configuration is missing connections"
        )

    for idx, conn in enumerate(details.connections):
        if not getattr(conn, "host", None) or not str(conn.host).strip():
            raise DIDSConnectionDetailsNotFoundError(
                f"Document Intelligence Data Server connection #{idx} is missing host"
            )
        if not getattr(conn, "port", None) or int(conn.port) <= 0:
            raise DIDSConnectionDetailsNotFoundError(
                f"Document Intelligence Data Server connection #{idx} has invalid port"
            )

    return details


DIDSDetailsDependency = Annotated[DIDSConnectionDetails, Depends(get_dids_connection_details)]


def get_docint_datasource(details: DIDSDetailsDependency) -> DataSource:
    """Ensure datasource setup for current configuration, then return it.

    Note: Uses a singleton service, mirroring other option services to avoid
    unsafe global caching patterns.
    """
    service = DocumentIntelligenceService.get_instance(details)
    return service.get_docint_datasource()


DocIntDatasourceDependency = Annotated[DataSource, Depends(get_docint_datasource)]
