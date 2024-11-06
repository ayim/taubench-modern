from abc import ABC, abstractmethod
from uuid import UUID

from langchain_core.vectorstores import VectorStore

from agent_server_types.models import MODEL


class VectorStoreBase(VectorStore, ABC):
    @abstractmethod
    async def adelete_by_file_id(self, file_id: str | UUID) -> None:
        """Delete a vector by it's metadata key file_id."""
        pass


class AgentServerKernalBase(ABC):
    """This class exposes Agent Server functionality to Agent Architecture
    plugins.

    This class is used to provide a common interface for interacting with
    the Agent Server from within an Agent Architecture plugin. The Agent
    Server will subclass this class and provide the necessary functionality
    to interact with the Agent Server, so when an Agent Architecture plugin
    is created, it can interact with the Agent Server without knowing the
    specifics of the Agent Server implementation.
    """

    @abstractmethod
    def get_vector_store(self, model: MODEL | None = None) -> VectorStoreBase:
        pass
