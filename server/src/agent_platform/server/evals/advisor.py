import logging
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
from agent_platform.server.evals.json import parse_json_object
from agent_platform.server.evals.retry import RetryExceededError, retry_async

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScenarioSuggestion:
    name: str
    description: str
    response_accuracy_expectation: str = ""


async def suggest_scenario_from_thread(user: User, thread: Thread, storage: StorageDependency):  # noqa: C901
    system_message = dedent("""
        You are an assistant that creates evaluation-ready scenario blueprints \
        from conversation threads. Each scenario suggestion must include: \
        - a concise, action-oriented name under 60 characters; \
        - a description that summarize the content of the conversation; \
        - a response accuracy expectation explaining the behaviors the agent \
          should exhibit to consider the run successful. \
        The expectation should summarize the desired steps or checks the agent performed \
        during the golden run, using short imperative sentences, one per line. \
        \
        Output ONLY valid JSON. Do not include extra commentary, markdown, \
        or formatting outside of the JSON.
    """)

    user_prompt_msg = dedent("""
        Given the following conversation thread, suggest an evaluation scenario. \
        The suggestion must include: \
        - "name": ≤60 characters, concise, action-oriented. \
        - "description": summarize the content of the conversation. \
        - "response_accuracy_expectation": list 2-5 short sentences (separated by newlines) \
          describing the behaviors the agent should demonstrate for a correct run. \
        \
        Thread: \
        \n \
        {exemplar_thread} \
        \n \
        Output RAW JSON only. Do not use code fences, markdown, or language tags. \
        The first character must be "{{" and the last must be "}}".
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

    def trim_initial_agents(messages):
        trimmed = []
        skip = True
        for m in messages:
            if skip and m.role == "agent":
                continue
            skip = False
            trimmed.append(m)
        return trimmed

    messages = trim_initial_agents(thread.messages)

    formatted_conversation_thread = await format_conversation(messages)

    user_prompt_msg = user_prompt_msg.format(
        exemplar_thread=formatted_conversation_thread,
    )

    async def _generate_once() -> ScenarioSuggestion:
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

        if not response.content:
            raise ValueError("No content returned by model")

        text_chunks = [c.text for c in response.content if isinstance(c, ResponseTextContent)]
        if not text_chunks:
            raise ValueError("No textual content returned by model")

        response_text = text_chunks[-1]
        logger.debug(f"Suggest scenario response: {response_text}")

        parsed_result = parse_json_object(response_text)
        parsed_result.setdefault("response_accuracy_expectation", "")

        try:
            return ScenarioSuggestion(**parsed_result)
        except TypeError as e:
            logger.debug(f"Parsed keys: {list(parsed_result.keys())}")
            raise ValueError("Parsed JSON does not match ScenarioSuggestion schema") from e

    def _on_error(exc: BaseException, attempt: int) -> None:
        logger.warning(f"Scenario suggestion attempt {attempt} failed: {exc}")

    try:
        suggestion = await retry_async(_generate_once, on_error=_on_error)
        return suggestion
    except RetryExceededError:
        logger.error("Scenario suggestion could not be parsed after retries")
        return None
