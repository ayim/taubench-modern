from dataclasses import dataclass

from sema4ai.actions import Response, action, chat


@dataclass
class _AgentContents:
    runbook: str | None
    action_stubs: str | None
    errors: list[str]


def _collect_agent_contents() -> _AgentContents:
    runbook = None
    action_stubs = None
    errors: list[str] = []
    try:
        runbook = chat.get_json(name="runbook.md")
    except Exception:
        errors.append("The runbook is missing!")
    try:
        action_stubs = chat.get_json(name="actions.py")
    except Exception:
        errors.append("The action stubs are missing!")
    return _AgentContents(runbook=runbook, action_stubs=action_stubs, errors=errors)


@action
def build_agent_zip() -> Response[str]:
    """
    Builds the agent zip file.
    """
    import io
    import zipfile

    agent_contents = _collect_agent_contents()
    if agent_contents.errors:
        return Response(
            error="The agent is not complete. Errors:\n"
            + "\n  ".join(agent_contents.errors)
        )
    runbook = agent_contents.runbook
    action_stubs = agent_contents.action_stubs
    assert runbook is not None
    assert action_stubs is not None

    chat.attach_json(
        "full-agent.json", {"runbook.md": runbook, "actions.py": action_stubs}
    )

    zip_bytes = io.BytesIO()
    with zipfile.ZipFile(zip_bytes, "w") as zip_file:
        zip_file.writestr("runbook.md", runbook)
        zip_file.writestr("actions.py", action_stubs)
    zip_bytes_value = zip_bytes.getvalue()
    chat.attach_file_content(name="full-agent.zip", data=zip_bytes_value)
    return Response(result="The agent was created successfully. ")

