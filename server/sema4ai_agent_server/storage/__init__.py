from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Union

from fastapi import HTTPException
from langchain_core.messages import AnyMessage

from sema4ai_agent_server.agent_types.constants import FINISH_NODE_KEY
from sema4ai_agent_server.schema import (
    MODEL,
    ActionPackage,
    Agent,
    AgentAdvancedConfig,
    AgentMetadata,
    EmbeddingStatus,
    Thread,
    UploadedFile,
    User,
)


class UniqueAgentNameError(HTTPException):
    def __init__(self, name: str, *args: object, **kwargs: object) -> None:
        super().__init__(status_code=409, detail=f"Agent '{name}' already exists")


class UniqueFileRefError(HTTPException):
    def __init__(self, file_ref: str, *args: object, **kwargs: object) -> None:
        super().__init__(status_code=409, detail=f"File '{file_ref}' already exists")


class BaseStorage(ABC):
    """Base class for storage backends."""

    @abstractmethod
    async def setup(self) -> None:
        """Setup the storage backend."""

    @abstractmethod
    async def teardown(self) -> None:
        """Teardown the storage backend."""

    @abstractmethod
    async def _run_migrations(self):
        pass

    async def list_agents(self, user_id: str) -> List[Agent]:
        """List all agents for the current user."""
        pass

    @abstractmethod
    async def list_all_agents(self) -> List[Agent]:
        """List all agents for all users."""
        pass

    @abstractmethod
    async def get_agent(self, user_id: str, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID."""
        pass

    @abstractmethod
    async def put_agent(
        self,
        user_id: str,
        agent_id: str,
        *,
        public: bool,
        name: str,
        description: str,
        runbook: str,
        version: str,
        model: MODEL,
        advanced_config: AgentAdvancedConfig,
        action_packages: list[ActionPackage],
        metadata: AgentMetadata,
    ) -> Agent:
        """Modify an agent."""
        pass

    @abstractmethod
    async def agent_count(self) -> int:
        """Get agent row count"""
        pass

    @abstractmethod
    async def list_threads(self, user_id: str) -> List[Thread]:
        """List all threads for the current user."""
        pass

    @abstractmethod
    async def get_thread(self, user_id: str, thread_id: str) -> Optional[Thread]:
        """Get a thread by ID."""
        pass

    @abstractmethod
    async def thread_count(self) -> int:
        """Get thread row count."""
        pass

    @abstractmethod
    async def get_thread_state(self, thread_id: str):
        """Get state for a thread."""
        pass

    @abstractmethod
    async def update_thread_state(
        self,
        thread_id: str,
        values: Union[Sequence[AnyMessage], Dict[str, Any]],
        as_node: Optional[str] = FINISH_NODE_KEY,
    ):
        """Add state to a thread."""
        pass

    @abstractmethod
    async def get_thread_history(self, thread_id: str):
        """Get the history of a thread."""
        pass

    @abstractmethod
    async def put_thread(
        self,
        user_id: str,
        thread_id: str,
        *,
        agent_id: str,
        name: str,
        metadata: Optional[dict],
    ) -> Thread:
        """Modify a thread."""
        pass

    @abstractmethod
    async def get_or_create_user(self, sub: str) -> tuple[User, bool]:
        """Returns a tuple of the user and a boolean indicating whether the user was created."""
        pass

    @abstractmethod
    async def delete_thread(self, user_id: str, thread_id: str):
        """Delete a thread by ID."""
        pass

    @abstractmethod
    async def delete_agent(self, user_id: str, agent_id: str) -> None:
        """Delete an agent by ID."""
        pass

    @abstractmethod
    async def get_agent_files(self, agent_id: str) -> list[UploadedFile]:
        """Get a list of files associated with an agent."""
        pass

    @abstractmethod
    async def get_thread_files(self, thread_id: str) -> list[UploadedFile]:
        """Get a list of files associated with a thread."""
        pass

    @abstractmethod
    async def get_file(
        self, owner: Union[Agent, Thread], file_ref: str
    ) -> Optional[UploadedFile]:
        """Get a file by ref."""
        pass

    @abstractmethod
    async def get_file_by_id(self, file_id: str) -> Optional[UploadedFile]:
        """Get a file by id."""
        pass

    @abstractmethod
    async def delete_file(self, file_id: str) -> None:
        """Delete a file by ID."""

    @abstractmethod
    async def put_file_owner(
        self,
        file_id: str,
        file_path: Optional[str],
        file_ref: str,
        file_hash: str,
        embedded: bool,
        embedding_status: Optional[EmbeddingStatus],
        owner: Union[Agent, Thread],
        file_path_expiration: Optional[datetime],
    ) -> UploadedFile:
        """Add or update a file owner."""
        pass

    @abstractmethod
    async def update_file_retrieve_information(
        self, file_id: str, *, file_path: str, file_path_expiration: datetime
    ) -> UploadedFile:
        """Update file retrieve information"""
        pass

    @abstractmethod
    async def update_file_embedding_status(
        self, file_id: str, *, embedding_status: EmbeddingStatus
    ) -> None:
        """Update file embedding status"""
        pass

    @abstractmethod
    async def create_async_run(self, run_id: str, status: str) -> None:
        pass

    @abstractmethod
    async def update_async_run(self, run_id: str, status: str) -> None:
        pass

    @abstractmethod
    async def get_async_run_status(self, run_id: str) -> Optional[str]:
        pass

    @abstractmethod
    async def list_agent_threads(self, agent_id: str) -> List[Thread]:
        """List all threads for the current agent."""
        pass
