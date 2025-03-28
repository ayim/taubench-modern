from agent_server_types_v2.kernel import FilesInterface
from sema4ai_agent_server.kernel.kernel_mixin import UsesKernelMixin


class AgentServerFilesInterface(FilesInterface, UsesKernelMixin):
    """Handles interaction with files uploaded during agent chat sessions."""

    async def todo(self) -> None:
        """TODO: figure out what methods we need here."""
        raise NotImplementedError("Not implemented")
