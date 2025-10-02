from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import sqlalchemy as sa

from agent_platform.core.agent import Agent
from agent_platform.core.config.config import Config
from agent_platform.core.data_server.data_connection import DataConnection
from agent_platform.core.data_server.data_server import DataServerDetails
from agent_platform.core.document_intelligence.integrations import DocumentIntelligenceIntegration
from agent_platform.core.files import UploadedFile
from agent_platform.core.kernel_interfaces.otel import OTelArtifact
from agent_platform.core.memory import Memory
from agent_platform.core.platforms.base import PlatformParameters
from agent_platform.core.runs import Run, RunStep
from agent_platform.core.storage import ScopedStorage
from agent_platform.core.thread import Thread, ThreadMessage
from agent_platform.core.user import User
from agent_platform.core.work_items import (
    WorkItem,
    WorkItemCompletedBy,
    WorkItemStatus,
    WorkItemStatusUpdatedBy,
)
from agent_platform.server.storage.types import JSONValue, StaleThreadsResult

if TYPE_CHECKING:
    from agent_platform.core import MCPServer, MCPServerSource
    from agent_platform.server.work_items.rest import AgentWorkItemsSummaryResponse


class AbstractStorage(ABC):
    """Pure abstract interface for storage backends.

    This class defines the contract that all storage implementations must follow.
    It contains only abstract methods with no concrete implementations.
    """

    @abstractmethod
    async def setup(self) -> None:
        """Run the migrations and any necessary setup."""

    @abstractmethod
    async def teardown(self) -> None:
        """Teardown logic, if needed."""

    @abstractmethod
    async def _run_migrations(self) -> None:
        """Run the migrations."""

    # -------------------------
    # Methods for agents
    # -------------------------
    @abstractmethod
    async def list_agents(self, user_id: str) -> list[Agent]:
        """List all agents for the given user."""

    @abstractmethod
    async def get_agent(self, user_id: str, agent_id: str) -> Agent:
        """Get an agent by ID."""

    @abstractmethod
    async def get_agent_by_name(self, user_id: str, name: str) -> Agent:
        """Get an agent by name."""

    @abstractmethod
    async def upsert_agent(self, user_id: str, agent: Agent) -> None:
        """Update (or insert) an agent."""

    @abstractmethod
    async def patch_agent(self, user_id: str, agent_id: str, name: str, description: str) -> None:
        """Update agent name and description."""

    @abstractmethod
    async def delete_agent(self, user_id: str, agent_id: str) -> None:
        """Delete an agent."""

    @abstractmethod
    async def count_agents(self) -> int:
        """Count the number of agents."""

    @abstractmethod
    async def count_agents_by_mode(self, mode: str) -> int:
        """Count the number of agents by mode."""

    @abstractmethod
    async def list_all_agents(self) -> list[Agent]:
        """List all agents for all users."""

    @abstractmethod
    async def get_agent_mcp_server_ids(self, agent_id: str) -> list[str]:
        """Get MCP server IDs associated with an agent."""

    @abstractmethod
    async def associate_mcp_servers_with_agent(
        self, agent_id: str, mcp_server_ids: list[str]
    ) -> None:
        """Associate MCP servers with an agent."""

    @abstractmethod
    async def get_agent_platform_params_ids(self, agent_id: str) -> list[str]:
        """Get platform params IDs associated with an agent."""

    @abstractmethod
    async def associate_platform_params_with_agent(
        self, agent_id: str, platform_params_ids: list[str]
    ) -> None:
        """Associate platform params with an agent."""

    # -------------------------
    # Methods for threads
    # -------------------------
    @abstractmethod
    async def list_threads(self, user_id: str) -> list[Thread]:
        """List all threads for the given user."""

    @abstractmethod
    async def list_threads_for_agent(
        self,
        user_id: str,
        agent_id: str,
    ) -> list[Thread]:
        """List all threads for the given agent."""

    @abstractmethod
    async def add_message_to_thread(
        self,
        user_id: str,
        thread_id: str,
        message: ThreadMessage,
    ) -> None:
        """Add a message to a thread."""

    @abstractmethod
    async def overwrite_thread_messages(
        self,
        thread_id: str,
        messages: list[ThreadMessage],
    ) -> None:
        """Overwrite the messages for the given thread."""

    @abstractmethod
    async def get_thread_messages(self, thread_id: str) -> list[ThreadMessage]:
        """Get messages for the given thread, in ascending sequence/creation order."""

    @abstractmethod
    async def get_messages_by_parent_run_id(
        self,
        user_id: str,
        parent_run_id: str,
    ) -> list[ThreadMessage]:
        """Get messages for the given parent run ID,
        in ascending sequence/creation order."""

    @abstractmethod
    async def get_thread(self, user_id: str, thread_id: str) -> Thread:
        """Get a thread by ID."""

    @abstractmethod
    async def upsert_thread(self, user_id: str, thread: Thread) -> None:
        """Update (or insert) a thread."""

    @abstractmethod
    async def delete_thread(self, user_id: str, thread_id: str) -> None:
        """Delete a thread."""

    @abstractmethod
    async def count_threads(self) -> int:
        """Count the number of threads."""

    @abstractmethod
    async def count_messages(self) -> int:
        """Count the number of messages."""

    @abstractmethod
    async def delete_threads_for_agent(
        self,
        user_id: str,
        agent_id: str,
        thread_ids: list[str] | None = None,
    ) -> None:
        """Delete specified threads, or all threads for a given agent
        and user if none are specified."""

    @abstractmethod
    async def trim_messages_from_sequence(
        self,
        user_id: str,
        thread_id: str,
        message_id: str,
    ) -> None:
        """Trim the messages from and after the given message_id,
        and return the trimmed messages."""

    # -------------------------
    # Methods for users
    # -------------------------
    @abstractmethod
    async def get_system_user_id(self) -> str:
        """Get the system user ID."""

    @abstractmethod
    async def get_or_create_user(self, sub: str) -> tuple[User, bool]:
        """
        Returns a tuple of the user and a boolean indicating whether
        the user was created.
        """

    @abstractmethod
    async def get_user_by_id(self, user_id: str) -> User:
        """Get a user by ID."""

    # -------------------------
    # Methods for runs and run steps
    # -------------------------
    @abstractmethod
    async def create_run(self, run: Run) -> None:
        """Create a new run record."""

    @abstractmethod
    async def get_run(self, run_id: str) -> Run:
        """Retrieve a run by its ID."""

    @abstractmethod
    async def list_runs_for_thread(self, thread_id: str) -> list[Run]:
        """List all runs associated with a given thread."""

    @abstractmethod
    async def upsert_run(self, run: Run) -> None:
        """Update (or insert) a run record."""

    @abstractmethod
    async def delete_run(self, run_id: str) -> None:
        """Delete a run record."""

    @abstractmethod
    async def create_run_step(self, run_step: RunStep) -> None:
        """Create a new run step record."""

    @abstractmethod
    async def list_run_steps(self, run_id: str) -> list[RunStep]:
        """List all run steps for a given run."""

    @abstractmethod
    async def get_run_step(self, step_id: str) -> RunStep:
        """Retrieve a run step by its ID."""

    # -------------------------
    # Methods for memory
    # -------------------------
    @abstractmethod
    async def create_memory(self, memory: Memory) -> None:
        """Create a new memory record."""

    @abstractmethod
    async def get_memory(self, memory_id: str) -> Memory:
        """Retrieve a memory record by its ID."""

    @abstractmethod
    async def list_memories(self, scope: str, scope_id: str) -> list[Memory]:
        """
        List memory records for a given scope.
        For example, scope might be 'user', 'agent', or 'thread'
        and scope_id the corresponding identifier.
        """

    @abstractmethod
    async def upsert_memory(self, memory: Memory) -> None:
        """Update (or insert) a memory record."""

    @abstractmethod
    async def delete_memory(self, memory_id: str) -> None:
        """Delete a memory record."""

    # -------------------------
    # Methods for scoped storage
    # -------------------------
    @abstractmethod
    async def create_scoped_storage(self, storage: ScopedStorage) -> None:
        """Create a new scoped storage record."""

    @abstractmethod
    async def get_scoped_storage(self, storage_id: str) -> ScopedStorage:
        """Retrieve a scoped storage record by its ID."""

    @abstractmethod
    async def list_scoped_storage(
        self,
        scope_type: str,
        scope_id: str,
    ) -> list[ScopedStorage]:
        """
        List all scoped storage records for a given scope type and scope identifier.
        For example, you might list all records for a given 'user', 'agent', or
        'thread'.
        """

    @abstractmethod
    async def upsert_scoped_storage(self, storage: ScopedStorage) -> None:
        """Update (or insert) a scoped storage record."""

    @abstractmethod
    async def delete_scoped_storage(self, storage_id: str) -> None:
        """Delete a scoped storage record."""

    # -------------------------
    # Methods for files
    # -------------------------
    @abstractmethod
    async def get_thread_files(
        self,
        thread_id: str,
        user_id: str,
    ) -> list[UploadedFile]:
        """Get a list of files associated with a thread."""

    @abstractmethod
    async def get_file_by_ref(
        self,
        owner: Agent | Thread | WorkItem,
        file_ref: str,
        user_id: str,
    ) -> UploadedFile | None:
        """Get a file by ref."""

    @abstractmethod
    async def delete_file(
        self,
        owner: Agent | Thread | WorkItem,
        file_id: str,
        user_id: str,
    ) -> None:
        """Delete a file by ref."""

    @abstractmethod
    async def delete_thread_files(
        self,
        thread_id: str,
        user_id: str,
    ) -> None:
        """Delete all files associated with a thread."""

    @abstractmethod
    async def get_file_by_id(
        self,
        file_id: str,
        user_id: str,
    ) -> UploadedFile | None:
        """Get a file by ID."""

    @abstractmethod
    async def put_file_owner(  # noqa: PLR0913
        self,
        file_id: str,
        file_path: str | None,
        file_ref: str,
        file_hash: str,
        file_size_raw: int,
        mime_type: str,
        user_id: str,
        embedded: bool,
        embedding_status: None,  # TODO: add a new type for EmbeddingStatus
        owner: Agent | Thread | WorkItem,
        file_path_expiration: datetime | None,
    ) -> UploadedFile:
        """Add or update a file owner."""

    @abstractmethod
    async def associate_work_item_file(
        self,
        file_id: str,
        work_item: WorkItem,
        agent_id: str,
        thread_id: str,
    ) -> None:
        """Associates an existing file with a agent_id and thread_id."""

    @abstractmethod
    async def update_file_retrieve_information(
        self,
        file_id: str,
        file_path: str,
        file_path_expiration: datetime,
        user_id: str,
    ) -> UploadedFile:
        """Update the file retrieve information."""

    # -------------------------
    # Methods for otel artifacts
    # -------------------------
    @abstractmethod
    async def get_otel_artifact(self, artifact_id: str) -> OTelArtifact:
        """Get an otel artifact by ID."""

    @abstractmethod
    async def get_otel_artifacts(
        self,
        artifact_ids: list[str] | None = None,
    ) -> list[OTelArtifact]:
        """Get a list of otel artifacts by IDs or all if ids is None."""

    @abstractmethod
    async def search_otel_artifacts(  # noqa: PLR0913
        self,
        trace_id: str | None = None,
        user_id: str | None = None,
        agent_id: str | None = None,
        thread_id: str | None = None,
        run_id: str | None = None,
        message_id: str | None = None,
    ) -> list[OTelArtifact]:
        """Search for otel artifacts by the given correlation IDs."""

    @abstractmethod
    async def create_otel_artifact(self, artifact: OTelArtifact) -> None:
        """Create a new otel artifact."""

    @abstractmethod
    async def cleanup_otel_artifacts(self) -> int:
        """Cleanup otel artifacts based on their expiration date."""

    @abstractmethod
    async def delete_all_otel_artifacts(self) -> int:
        """Delete all otel artifacts."""

    # -------------------------
    # Methods for work items
    # -------------------------
    @abstractmethod
    async def create_work_item(self, work_item: WorkItem) -> None:
        """Create a new work item."""

    @abstractmethod
    async def get_work_item(self, work_item_id: str) -> WorkItem:
        """Get a work item by ID."""

    @abstractmethod
    async def get_work_items_by_ids(self, work_item_ids: list[str]) -> list[WorkItem]:
        """Get work items by IDs."""

    @abstractmethod
    async def list_work_items(
        self,
        agent_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
        created_by: str | None = None,
    ) -> list[WorkItem]:
        """List all work items for the given user and agent."""

    @abstractmethod
    async def update_work_item_status(
        self,
        user_id: str,
        work_item_id: str,
        status: WorkItemStatus,
        status_updated_by: WorkItemStatusUpdatedBy = WorkItemStatusUpdatedBy.SYSTEM,
    ) -> None:
        """Update the status of a work item."""

    @abstractmethod
    async def complete_work_item(
        self,
        user_id: str,
        work_item_id: str,
        completed_by: WorkItemCompletedBy,
    ) -> None:
        """Complete a work item with the specified completed_by value."""

    @abstractmethod
    async def get_pending_work_item_ids(self, limit: int = 10) -> list[str]:
        """Get the IDs of work items that are next to be processed."""

    @abstractmethod
    async def mark_incomplete_work_items_as_error(self, work_item_ids: list[str]) -> None:
        """Mark given work items as ERROR if they are still PENDING/EXECUTING."""

    @abstractmethod
    async def get_work_items_summary(self, user_id: str) -> list["AgentWorkItemsSummaryResponse"]:
        """Get work items summary grouped by agent and status.

        Returns a list of AgentWorkItemsSummaryResponse objects.
        """

    # -------------------------
    # Methods for MCP servers
    # -------------------------
    @abstractmethod
    async def create_mcp_server(self, mcp_server: "MCPServer", source: "MCPServerSource") -> str:
        """Create a new MCP server. Returns the generated MCP server ID."""

    @abstractmethod
    async def get_mcp_server(self, mcp_server_id: str) -> "MCPServer":
        """Get an MCP server by ID."""

    @abstractmethod
    async def get_mcp_server_with_metadata(
        self, mcp_server_id: str
    ) -> tuple["MCPServer", "MCPServerSource"]:
        """Get an MCP server by ID with its source information."""

    @abstractmethod
    async def list_mcp_servers(self) -> dict[str, "MCPServer"]:
        """List all MCP servers."""

    @abstractmethod
    async def list_mcp_servers_with_metadata(
        self,
    ) -> dict[str, tuple["MCPServer", "MCPServerSource"]]:
        """List all MCP servers with their source information."""

    @abstractmethod
    async def get_mcp_server_by_name(
        self, name: str, source: "MCPServerSource"
    ) -> tuple[str, "MCPServer", "MCPServerSource"] | None:
        """Get an MCP server by name"""

    @abstractmethod
    async def list_mcp_servers_by_source(self, source: "MCPServerSource") -> dict[str, str]:
        """List MCP servers by source. Returns dict of {name: mcp_server_id}."""

    @abstractmethod
    async def update_mcp_server(
        self,
        mcp_server_id: str,
        mcp_server: "MCPServer",
        mcp_server_source: "MCPServerSource",
    ) -> None:
        """Update an MCP server."""

    @abstractmethod
    async def delete_mcp_server(self, mcp_server_ids: list[str]) -> None:
        """Delete MCP servers."""

    @abstractmethod
    async def count_mcp_servers(self) -> int:
        """Count the number of MCP servers."""

    @abstractmethod
    async def get_mcp_servers_by_ids(self, mcp_server_ids: list[str]) -> dict[str, "MCPServer"]:
        """Get multiple MCP servers by their IDs."""

    @abstractmethod
    async def update_work_item_from_thread(
        self,
        user_id: str,
        work_item_id: str,
        thread_id: str,
    ) -> None:
        """Update a work item from a thread.

        This is used to update the work item with the thread ID
        and the thread messages.
        """

    @abstractmethod
    async def update_work_item(self, work_item: WorkItem) -> None:
        """Update a work item."""

    @abstractmethod
    async def get_workitem_files(self, work_item_id: str, user_id: str) -> list[UploadedFile]:
        """Get all files associated with a work item."""

    # -------------------------------------------------------------------------
    # Methods for platform parameters
    # -------------------------------------------------------------------------
    @abstractmethod
    async def create_platform_params(
        self,
        platform_params: PlatformParameters,
    ) -> None:
        """Create a new platform configuration."""

    @abstractmethod
    async def get_platform_params(
        self,
        platform_params_id: str,
    ) -> PlatformParameters:
        """Get a platform configuration by ID."""

    @abstractmethod
    async def list_platform_params(self) -> list[PlatformParameters]:
        """List all platform configurations."""

    @abstractmethod
    async def update_platform_params(
        self,
        platform_params_id: str,
        platform_params: PlatformParameters,
    ) -> None:
        """Update a platform configuration."""

    @abstractmethod
    async def delete_platform_params(self, platform_params_id: str) -> None:
        """Delete a platform configuration."""

    # -------------------------------------------------------------------------
    # Methods for Document Intelligence
    # -------------------------------------------------------------------------
    @abstractmethod
    async def get_dids_connection_details(self) -> DataServerDetails:
        """Get the Document Intelligence Data Server connection details."""

    @abstractmethod
    async def set_dids_connection_details(self, details: DataServerDetails) -> None:
        """Set the Document Intelligence Data Server connection details."""

    @abstractmethod
    async def delete_dids_connection_details(self) -> None:
        """Delete the Document Intelligence Data Server connection details."""

    @abstractmethod
    async def get_document_intelligence_integration(
        self, kind: str
    ) -> DocumentIntelligenceIntegration:
        """Get a document intelligence integration by kind."""

    @abstractmethod
    async def list_document_intelligence_integrations(
        self,
    ) -> list[DocumentIntelligenceIntegration]:
        """List all document intelligence integrations."""

    @abstractmethod
    async def set_document_intelligence_integration(
        self, integration: DocumentIntelligenceIntegration
    ) -> DocumentIntelligenceIntegration:
        """Create or update a document intelligence integration."""

    @abstractmethod
    async def delete_document_intelligence_integration(self, kind: str) -> None:
        """Delete a document intelligence integration by kind."""

    @abstractmethod
    async def get_dids_data_connections(self) -> list[DataConnection]:
        """Get all Document Intelligence Data Server data connections."""

    @abstractmethod
    async def set_dids_data_connections(self, data_connections: list[DataConnection]) -> None:
        """Set Document Intelligence Data Server data connections (replace all)."""

    # -------------------------------------------------------------------------
    # Methods for Agent Config
    # -------------------------------------------------------------------------
    @abstractmethod
    async def list_all_configs(self) -> list[Config]:
        """Fetches the list of all available agent configs from DB"""

    @abstractmethod
    async def get_config(self, config_type: str, *, namespace: str = "global") -> Config:
        """Fetches the config from the DB for the config_type

        Args:
            config_type: Must be one of the valid ConfigType values defined in quotas.py
        """

    @abstractmethod
    async def set_config(
        self, config_type: str, current_value: JSONValue, *, namespace: str = "global"
    ):
        """Sets the config value in the DB for the config_type

        Args:
            config_type: Must be one of the valid ConfigType values defined in quotas.py
            current_value: The new configuration value as a string
        """

    @abstractmethod
    def _clean_up_stale_threads__get_threshold(self, now: datetime, config_column: sa.Column):
        """Get Interval for cleaning up stale threads."""

    @abstractmethod
    async def clean_up_stale_threads(
        self, default_retention_period: timedelta
    ) -> list[StaleThreadsResult]:
        """Cleans up stale threads based on the configured retention period."""
