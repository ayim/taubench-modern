from abc import ABC, abstractmethod

from agent_server_types_v2.agent import Agent
from agent_server_types_v2.memory import Memory
from agent_server_types_v2.runs import Run, RunStep
from agent_server_types_v2.storage import ScopedStorage
from agent_server_types_v2.thread import Thread, ThreadMessage
from agent_server_types_v2.user import User


class BaseStorageV2(ABC):
    """Base class for the new v2 storage backends."""

    @abstractmethod
    async def setup_v2(self) -> None:
        """Run the v2 migrations and any necessary setup."""
        pass

    @abstractmethod
    async def teardown_v2(self) -> None:
        """Teardown logic for v2, if needed."""
        pass

    @abstractmethod
    async def _run_migrations(self) -> None:
        """Run the v2 migrations."""
        pass

    # -------------------------
    # Methods for agents
    # -------------------------
    @abstractmethod
    async def list_agents_v2(self, user_id: str) -> list[Agent]:
        """List all agents for the given user."""
        pass

    @abstractmethod
    async def list_all_agents_v2(self) -> list[Agent]:
        """List all agents for all users."""
        pass

    @abstractmethod
    async def get_agent_v2(self, user_id: str, agent_id: str) -> Agent:
        """Get an agent by ID."""
        pass

    @abstractmethod
    async def get_agent_by_name_v2(self, user_id: str, name: str) -> Agent:
        """Get an agent by name."""
        pass

    @abstractmethod
    async def upsert_agent_v2(self, user_id: str, agent: Agent) -> None:
        """Update (or insert) an agent."""
        pass

    @abstractmethod
    async def delete_agent_v2(self, user_id: str, agent_id: str) -> None:
        """Delete an agent."""
        pass

    @abstractmethod
    async def count_agents_v2(self) -> int:
        """Count the number of agents."""
        pass

    # -------------------------
    # Methods for threads
    # -------------------------
    @abstractmethod
    async def list_threads_v2(self, user_id: str) -> list[Thread]:
        """List all threads for the given user."""
        pass

    @abstractmethod
    async def list_threads_for_agent_v2(self, user_id: str, agent_id: str) -> list[Thread]:
        """List all threads for the given agent."""
        pass

    @abstractmethod
    async def add_message_to_thread_v2(self, user_id: str, thread_id: str, message: ThreadMessage) -> None:
        """Add a message to a thread."""
        pass

    @abstractmethod
    async def get_thread_v2(self, user_id: str, thread_id: str) -> Thread:
        """Get a thread by ID."""
        pass

    @abstractmethod
    async def upsert_thread_v2(self, user_id: str, thread: Thread) -> None:
        """Update (or insert) a thread."""
        pass

    @abstractmethod
    async def delete_thread_v2(self, user_id: str, thread_id: str) -> None:
        """Delete a thread."""
        pass

    @abstractmethod
    async def count_threads_v2(self) -> int:
        """Count the number of threads."""
        pass

    # -------------------------
    # Methods for users
    # -------------------------
    @abstractmethod
    async def get_system_user_id_v2(self) -> str:
        """Get the system user ID."""
        pass

    @abstractmethod
    async def get_or_create_user_v2(self, sub: str) -> tuple[User, bool]:
        """
        Returns a tuple of the user and a boolean indicating whether the user was created.
        """
        pass

    @abstractmethod
    async def delete_user_v2(self, user_id: str) -> None:
        """Delete a user by ID."""
        pass

    # -------------------------
    # Methods for runs and run steps
    # -------------------------
    @abstractmethod
    async def create_run_v2(self, run: Run) -> None:
        """Create a new run record."""
        pass

    @abstractmethod
    async def get_run_v2(self, run_id: str) -> Run:
        """Retrieve a run by its ID."""
        pass

    @abstractmethod
    async def list_runs_for_thread_v2(self, thread_id: str) -> list[Run]:
        """List all runs associated with a given thread."""
        pass

    @abstractmethod
    async def upsert_run_v2(self, run: Run) -> None:
        """Update (or insert) a run record."""
        pass

    @abstractmethod
    async def delete_run_v2(self, run_id: str) -> None:
        """Delete a run record."""
        pass

    @abstractmethod
    async def create_run_step_v2(self, run_step: RunStep) -> None:
        """Create a new run step record."""
        pass

    @abstractmethod
    async def list_run_steps_v2(self, run_id: str) -> list[RunStep]:
        """List all run steps for a given run."""
        pass

    @abstractmethod
    async def get_run_step_v2(self, step_id: str) -> RunStep:
        """Retrieve a run step by its ID."""
        pass

    # -------------------------
    # Methods for memory
    # -------------------------
    @abstractmethod
    async def create_memory_v2(self, memory: Memory) -> None:
        """Create a new memory record."""
        pass

    @abstractmethod
    async def get_memory_v2(self, memory_id: str) -> Memory:
        """Retrieve a memory record by its ID."""
        pass

    @abstractmethod
    async def list_memories_v2(self, scope: str, scope_id: str) -> list[Memory]:
        """
        List memory records for a given scope.
        For example, scope might be 'user', 'agent', or 'thread'
        and scope_id the corresponding identifier.
        """
        pass

    @abstractmethod
    async def upsert_memory_v2(self, memory: Memory) -> None:
        """Update (or insert) a memory record."""
        pass

    @abstractmethod
    async def delete_memory_v2(self, memory_id: str) -> None:
        """Delete a memory record."""
        pass

    # -------------------------
    # Methods for scoped storage
    # -------------------------
    @abstractmethod
    async def create_scoped_storage_v2(self, storage: ScopedStorage) -> None:
        """Create a new scoped storage record."""
        pass

    @abstractmethod
    async def get_scoped_storage_v2(self, storage_id: str) -> ScopedStorage:
        """Retrieve a scoped storage record by its ID."""
        pass

    @abstractmethod
    async def list_scoped_storage_v2(self, scope_type: str, scope_id: str) -> list[ScopedStorage]:
        """
        List all scoped storage records for a given scope type and scope identifier.
        For example, you might list all records for a given 'user', 'agent', or 'thread'.
        """
        pass

    @abstractmethod
    async def upsert_scoped_storage_v2(self, storage: ScopedStorage) -> None:
        """Update (or insert) a scoped storage record."""
        pass

    @abstractmethod
    async def delete_scoped_storage_v2(self, storage_id: str) -> None:
        """Delete a scoped storage record."""
        pass
