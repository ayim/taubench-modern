from sema4ai.actions import action, Response, chat
from typing import  Annotated
from dataclasses import dataclass

@dataclass
class FileResponse:
    file_name: Annotated[str, "The name of the file that was saved."]
    details: Annotated[str, "Details about the file that was saved."]

FILE_NAME = "full-action-contents.json"


@action
def save_runbook(runbook: str) -> Response[FileResponse]:
    """
    Saves the runbook that will be used by the agent.

    Args:
        runbook: The runbook as a markdown string.

    Returns:
        A response with the reference to the file which contains
        the full content to create the agent (it has the runbook,
        and actions).
    """
    details = "The runbook was saved successfully."
    try:
        current_contents = chat.get_json(FILE_NAME)
    except Exception:
        current_contents = {}
    current_contents['runbook'] = runbook
    chat.attach_json(name=FILE_NAME, contents=current_contents)
    return Response(result=FileResponse(file_name=FILE_NAME, details=details))


