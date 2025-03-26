from abc import ABC, abstractmethod

from agent_server_types_v2.runbook import Runbook
from agent_server_types_v2.runbook.content import RunbookStepsContent


class RunbookInterface(ABC):
    """Manages interaction with the agent's natural language runbook
    and its structured data."""

    @abstractmethod
    async def get_runbook(self) -> Runbook:
        """Returns the full runbook.

        Returns:
            The runbook object.
        """
        pass

    @abstractmethod
    async def runbook_has_steps(self) -> bool:
        """Returns True if the runbook has steps with appropriate
        structured metadata and False otherwise.

        Returns:
            True if the runbook has steps, False otherwise.
        """
        pass

    @abstractmethod
    async def get_runbook_steps(self) -> RunbookStepsContent:
        """Returns the runbook steps as a StepsContent object.

        Returns:
            The runbook steps content.
        """
        pass
