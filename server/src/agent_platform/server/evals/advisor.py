from dataclasses import dataclass
from textwrap import dedent
from typing import cast

from fastapi import Request

from agent_platform.architectures.default.thread_conversion import (
    thread_messages_to_prompt_messages,
)
from agent_platform.core.context import AgentServerContext
from agent_platform.core.prompts.content.text import PromptTextContent
from agent_platform.core.prompts.messages import PromptUserMessage
from agent_platform.core.prompts.prompt import Prompt
from agent_platform.core.responses.content.text import ResponseTextContent
from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.thread import Thread
from agent_platform.core.user import User
from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.api.private_v2.prompt import prompt_generate
from agent_platform.server.api.private_v2.utils import create_minimal_kernel


@dataclass(frozen=True)
class ScenarioSuggestion:
    name: str
    description: str
    rationale: str


async def suggest_scenario_from_thread(user: User, thread: Thread, storage: StorageDependency):
    system_message = dedent("""
        You are an assistant that helps generate concise and meaningful \
        scenario blueprints from conversation threads. \
        A scenario consists of a short, descriptive name and a short description \
        of what the thread is supposed to accomplish. \
        Always keep names clear, action-oriented, and under 60 characters. \
        Descriptions should capture the purpose or outcome, not the implementation details. \
        \
        Output ONLY valid JSON. Do not include extra commentary, markdown, \
        or formatting outside of the JSON.
    """)

    user_prompt_msg = dedent("""
        Given the following conversation thread, suggest a scenario name and description. \
        The suggestion must have: \
        - A name (≤60 characters, concise, action-oriented). \
        - A description explaining the purpose. \
        - A rationale for why this suggestion fits. \
        \
        Thread: \
        \n \
        {exemplar_thread} \
        \n \
        Output ONLY valid JSON. Do not include extra commentary, markdown, \
        or formatting outside of the JSON.
    """)

    mock_request = Request(scope={"type": "http", "method": "POST"})
    ctx = AgentServerContext.from_request(
        request=mock_request,
        user=user,
        version="2.0.0",
    )
    kernel = create_minimal_kernel(ctx)
    kernel.converters.set_thread_message_conversion_function(
        thread_messages_to_prompt_messages,
    )

    async def format_conversation(messages: list[ThreadMessage]):
        converted_messages = await kernel.converters.thread_messages_to_prompt_messages(messages)
        temp_prompt = Prompt(messages=cast(list, converted_messages))
        return temp_prompt.to_pretty_yaml(include=["messages"])

    formatted_conversation_thread = await format_conversation(thread.messages)

    user_prompt_msg = user_prompt_msg.format(
        exemplar_thread=formatted_conversation_thread,
    )

    prompt = Prompt(
        system_instruction=system_message,
        messages=[PromptUserMessage(content=[PromptTextContent(text=user_prompt_msg)])],
        temperature=0.0,
    )
    response = await prompt_generate(
        prompt,
        user=user,
        storage=storage,
        request=Request(scope={"type": "http", "method": "POST"}),
        agent_id=thread.agent_id,
    )

    import json

    content = next(
        (item for item in response.content if isinstance(item, ResponseTextContent)), None
    )
    if content is None:
        raise RuntimeError("expected ResponseTextContent")

    suggestion_data = content.text
    suggestion_json = json.loads(suggestion_data)
    return ScenarioSuggestion(**suggestion_json)
