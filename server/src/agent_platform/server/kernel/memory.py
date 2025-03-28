from agent_platform.core.kernel import MemoryInterface
from agent_platform.core.memory import Memory
from agent_platform.server.kernel.kernel_mixin import UsesKernelMixin


class AgentServerMemoryInterface(MemoryInterface, UsesKernelMixin):
    """Manages agent memory operations including reading and writing."""

    async def put_memory(self, memory: Memory) -> None:
        """Puts memory into the memory store.

        Arguments:
            memory: The memory object to store.
        """
        raise NotImplementedError("Not implemented")

    async def get_memory_by_id(self, memory_id: str) -> Memory:
        """Retrieves memory from the memory store by its ID.

        Arguments:
            memory_id: The ID of the memory to retrieve.

        Returns:
            The retrieved memory object.
        """
        raise NotImplementedError("Not implemented")

    async def retrieve_relevant_memories(
        self,
        query: str,
        top_n: int = 10,
    ) -> list[Memory]:
        """Retrieves relevant memories from the memory store based on a query.

        Uses embeddings to find relevant memories.

        Arguments:
            query: The query to search for relevant memories.
            top_n: The number of memories to return.

        Returns:
            A list of relevant memories.
        """
        raise NotImplementedError("Not implemented")

    async def retrieve_relevant_memories_by_text(
        self,
        text: str,
        top_n: int = 10,
    ) -> list[Memory]:
        """Retrieves relevant memories from the memory store based on a text fragment.

        Uses text search to find relevant memories.

        Arguments:
            text: The text to search for relevant memories.
            top_n: The number of memories to return.

        Returns:
            A list of relevant memories.
        """
        raise NotImplementedError("Not implemented")

    async def delete_memory(self, memory_id: str) -> None:
        """Deletes memory from the memory store by its ID.

        Arguments:
            memory_id: The ID of the memory to delete.
        """
        raise NotImplementedError("Not implemented")
