from agent_platform.core.kernel import FilesInterface
from agent_platform.server.kernel.kernel_mixin import UsesKernelMixin


class AgentServerFilesInterface(FilesInterface, UsesKernelMixin):
    """Handles interaction with files uploaded during agent chat sessions."""

    async def todo(self) -> None:
        """TODO: figure out what methods we need here."""
        raise NotImplementedError("Not implemented")
