from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Union

from langchain_core.messages import AnyMessage

from sema4ai_agent_server.agent_types.constants import FINISH_NODE_KEY
from sema4ai_agent_server.schema import Agent, Thread, UploadedFile, User


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
        name: str,
        config: dict,
        public: bool = False,
        metadata: Optional[dict],
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
    async def get_thread_state(self, user_id: str, thread_id: str):
        """Get state for a thread."""
        pass

    @abstractmethod
    async def update_thread_state(
        self,
        user_id: str,
        thread_id: str,
        values: Union[Sequence[AnyMessage], Dict[str, Any]],
        as_node: Optional[str] = FINISH_NODE_KEY,
    ):
        """Add state to a thread."""
        pass

    @abstractmethod
    async def get_thread_history(self, user_id: str, thread_id: str):
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
