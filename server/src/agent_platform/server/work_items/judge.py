import logging
from textwrap import dedent
from typing import cast

from fastapi import Request

from agent_platform.architectures.default.thread_conversion import (
    thread_messages_to_prompt_messages,
)
from agent_platform.core.context import AgentServerContext
from agent_platform.core.prompts import Prompt
from agent_platform.core.prompts.content.text import PromptTextContent
from agent_platform.core.prompts.messages import PromptUserMessage
from agent_platform.core.responses.content.text import ResponseTextContent
from agent_platform.core.work_items import (
    WorkItem,
    WorkItemStatus,
)
from agent_platform.server.api.private_v2.prompt import prompt_generate
from agent_platform.server.api.private_v2.utils import create_minimal_kernel
from agent_platform.server.storage import StorageService

logger = logging.getLogger(__name__)


def _load_judge_prompt() -> str:
    """Load the judge prompt from the bundled resources.

    Uses importlib.resources for development and sys._MEIPASS for PyInstaller
    bundled environments.

    Returns:
        The judge prompt content as a string.
    """
    import sys
    from pathlib import Path

    from agent_platform.server.constants import IS_FROZEN

    if IS_FROZEN:
        # PyInstaller bundle - use sys._MEIPASS
        base_path = Path(getattr(sys, "_MEIPASS"))  # noqa: B009
        judge_prompt_path = base_path / "agent_platform" / "server" / "work_items" / "judge_prompt.txt"
        content = judge_prompt_path.read_text(encoding="utf-8")
    else:
        # Development environment - use importlib.resources
        from importlib import resources

        package_resources = resources.files("agent_platform.server.work_items")
        judge_prompt_resource = package_resources / "judge_prompt.txt"
        content = judge_prompt_resource.read_text(encoding="utf-8")

    return dedent(content)


async def _validate_success(item: WorkItem) -> WorkItemStatus:
    # 1. System message describing the judge's role
    system_message = dedent("""
        You are an expert evaluator of LLM conversations. Your role is to assess whether \
        an AI agent successfully completed the task given to it by the user by analyzing the \
        conversation history between the agent and user. The AI Agent is responsible for \
        using data, tools and other resources to accomplish a business task
        which a human would have previously done. Agents often have tools to verify that
        they have completed the task successfully -- when these tasks fail (including reasons
        where the business logic verification fails), this means that the agent has failed
        to complete the task successfully.
    """)

    # 2-5. Combined judgment prompt with criteria, primer, messages, and final instructions
    judge_prompt_msg = _load_judge_prompt()

    storage = StorageService.get_instance()
    user = await storage.get_user_by_id(item.user_id)

    # Create a minimal kernel context to access the converters interface
    mock_request = Request(scope={"type": "http", "method": "POST"})
    ctx = AgentServerContext.from_request(
        request=mock_request,
        user=user,
        version="2.0.0",
    )
    kernel = create_minimal_kernel(ctx)

    # Use the existing thread-to-prompt message converter
    # TODO: using the message conversion for the default arch, but work items
    # could have it's _own_ conversion tailored to the judgement task
    kernel.converters.set_thread_message_conversion_function(
        thread_messages_to_prompt_messages,
    )
    converted_messages = await kernel.converters.thread_messages_to_prompt_messages(item.messages)
    # Format the conversation thread through a temporary prompt instance
    temp_prompt = Prompt(messages=cast(list, converted_messages))
    formatted_conversation_thread = temp_prompt.to_pretty_yaml(include=["messages"])
    judge_prompt_msg = judge_prompt_msg.format(conversation_thread=formatted_conversation_thread)

    prompt = Prompt(
        system_instruction=system_message,
        messages=[PromptUserMessage(content=[PromptTextContent(text=judge_prompt_msg)])],
        temperature=0.0,
    )
    result = await prompt_generate(
        prompt,
        user=user,
        storage=storage,
        request=Request(scope={"type": "http", "method": "POST"}),
        agent_id=item.agent_id,
    )
    if content := result.content:
        if text_content := [c.text for c in content if isinstance(c, ResponseTextContent)]:
            response_text = text_content[-1]
            logger.debug(f"Work item validation response: {response_text}")

            # Extract the classification from the structured response
            for line in response_text.split("\n"):
                clean_line = line.strip()
                if clean_line.startswith("CLASSIFICATION:"):
                    classification = clean_line.split("CLASSIFICATION:", 1)[1].strip()
                    try:
                        return WorkItemStatus(classification)
                    except ValueError:
                        logger.warning(f"Work item validation failed: invalid classification: {classification}")
                        break

            # Fallback: try to parse the entire response as before (for backward compatibility)
            try:
                return WorkItemStatus(response_text.strip())
            except ValueError:
                logger.warning(f"Work item validation failed: could not parse response: {response_text!r}")
                pass
    # If we get here, the work item validation failed; return INDETERMINATE
    return WorkItemStatus.INDETERMINATE
