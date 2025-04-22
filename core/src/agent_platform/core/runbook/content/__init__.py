"""RunbookContent: types defining the content of a runbook."""

from agent_platform.core.runbook.content.base import RunbookContent
from agent_platform.core.runbook.content.step import RunbookStepContent
from agent_platform.core.runbook.content.steps import RunbookStepsContent
from agent_platform.core.runbook.content.text import RunbookTextContent

AnyRunbookContent = RunbookStepContent | RunbookStepsContent | RunbookTextContent

__all__ = [
    "RunbookContent",
    "RunbookStepContent",
    "RunbookStepsContent",
    "RunbookTextContent",
    "AnyRunbookContent",
]
