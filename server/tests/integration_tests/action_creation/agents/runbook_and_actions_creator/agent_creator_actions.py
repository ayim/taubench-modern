from dataclasses import dataclass

from sema4ai.actions import ActionError, Response, action, chat


@action
def save_runbook(runbook: str) -> Response[str]:
    """
    Saves the runbook that will be used by the agent.

    Args:
        runbook: The runbook as a markdown string.

    Returns:
        A response with the reference to the file which contains
        the full content to create the agent (it has the runbook,
        and action stubs).
    """
    chat.attach_json(name="runbook.md", contents=runbook)
    return Response(
        result="The runbook was saved successfully. Remember to call `is_agent_complete()` to check if the agent is complete."
    )


@action
def save_action_stubs(action_stubs_code: str) -> Response[str]:
    """
    Saves the python code with the action stubs that will be used by the agent.

    Args:
        action_stubs_code: The python code with the action stubs.

    Returns:
        A response with the reference to the file which contains
        the full content to create the agent (it has the runbook,
        and action stubs).
    """
    chat.attach_json(name="actions.py", contents=action_stubs_code)
    return Response(
        result="The action stubs were saved successfully. Remember to call `is_agent_complete()` to check if the agent is complete."
    )


@action
def is_agent_complete() -> Response[str]:
    """
    Checks if the agent is complete (either returns an error or a success message).
    """
    agent_contents = _collect_agent_contents()
    if agent_contents.errors:
        return Response(
            error="The agent is not complete. Errors:\n"
            + "\n  ".join(agent_contents.errors)
        )
    return Response(result="The agent is now complete.")


def validate_action_stubs(action_stubs_code: str):
    import subprocess

    try:
        compile(action_stubs_code, "<string>", "exec")
    except Exception as e:
        raise ActionError(f"The action stubs are not valid: {e}")

    # Ok, the syntax seems to be correct, now, use ruff to check for errors
    import ruff.__main__

    ruff_bin = ruff.__main__.find_ruff_bin()
    ruff_process = subprocess.run(
        [
            ruff_bin,
            "--quiet",
            "--stdin-filename",
            "<string>",
            "--stdin",
            action_stubs_code,
        ]
    )
    if ruff_process.returncode != 0:
        raise ActionError(
            f"The action stubs are not valid: {ruff_process.stderr.decode('utf-8')}"
        )


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
        errors.append(
            "The runbook is missing (remember to call `save_runbook()` with the runbook)."
        )
    try:
        action_stubs = chat.get_json(name="actions.py")
    except Exception:
        errors.append(
            "The action stubs are missing (remember to call `save_action_stubs()` with the action stubs)."
        )
    return _AgentContents(runbook=runbook, action_stubs=action_stubs, errors=errors)
