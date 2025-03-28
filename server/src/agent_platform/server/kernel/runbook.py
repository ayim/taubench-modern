from agent_platform.core.kernel import RunbookInterface
from agent_platform.core.runbook import Runbook
from agent_platform.core.runbook.content import RunbookStepsContent
from agent_platform.server.kernel.kernel_mixin import UsesKernelMixin


class AgentServerRunbookInterface(RunbookInterface, UsesKernelMixin):
    """Manages interaction with the agent's natural language runbook
    and its structured data."""

    async def get_runbook(self) -> Runbook:
        """Returns the full runbook.

        Returns:
            The runbook object.
        """
        raise NotImplementedError("Not implemented")

    async def runbook_has_steps(self) -> bool:
        """Returns True if the runbook has steps with appropriate
        structured metadata and False otherwise.

        Returns:
            True if the runbook has steps, False otherwise.
        """
        raise NotImplementedError("Not implemented")

    async def get_runbook_steps(self) -> RunbookStepsContent:
        """Returns the runbook steps as a StepsContent object.

        Returns:
            The runbook steps content.
        """
        raise NotImplementedError("Not implemented")
