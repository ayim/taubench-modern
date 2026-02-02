import logging
from textwrap import dedent

from fastapi import Request

from agent_platform.architectures.default.thread_conversion import (
    thread_messages_to_prompt_messages,
)
from agent_platform.core.context import AgentServerContext
from agent_platform.core.errors.responses import ErrorCode
from agent_platform.core.evals.types import (
    EvaluationResult,
    ResponseAccuracyResult,
    Scenario,
)
from agent_platform.core.prompts import Prompt
from agent_platform.core.prompts.content.text import PromptTextContent
from agent_platform.core.prompts.messages import PromptUserMessage
from agent_platform.core.responses.content import ResponseTextContent
from agent_platform.core.thread.thread import Thread
from agent_platform.core.user import User
from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.api.private_v2.prompt import prompt_generate
from agent_platform.server.api.private_v2.utils import create_minimal_kernel
from agent_platform.server.evals.conversation_formatting import (
    format_thread_conversation_for_eval,
)
from agent_platform.server.evals.errors import is_rate_limit_error, log_and_format_error
from agent_platform.server.evals.json import parse_json_object
from agent_platform.server.evals.retry import RetryExceededError, retry_async

logger = logging.getLogger(__name__)


async def evaluate_response_accuracy(
    thread: Thread,
    scenario: Scenario,
    user: User,
    storage: StorageDependency,
    criteria: str,
) -> EvaluationResult:
    system_message = dedent("""
        You are an expert evaluator of LLM conversations. \
        Your role is to analyse the conversation history between the agent and user. \
        Provide accurate, objective evaluations.
    """)

    judge_prompt_msg = dedent("""
        Please evaluate if the target conversation is accurate based on CRITERIA. \
        CRITERIA: \
        {criteria} \
        CONVERSATION: \
        {target_conversation} \
        Please respond with a JSON object containing (in this order): \
        - "explanation": a brief explanation of your thoughts/evaluation \
        - "score": a number from 0-10 indicating quality (10 = perfect match) \
        - "passed": true/false indicating if the response meets the criteria (score >= 6) \
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

    formatted_target_conversation_thread = await format_thread_conversation_for_eval(
        kernel=kernel,
        messages=thread.messages,
    )

    user_prompt_msg = judge_prompt_msg.format(
        target_conversation=formatted_target_conversation_thread,
        criteria=criteria,
    )

    from agent_platform.server.evals.utils import resolve_global_eval_model

    eval_model, eval_platform_params = await resolve_global_eval_model(storage)
    logger.info(
        "Response Accuracy judge platform params selection: eval_model=%s eval_platform_params=%s agent_id=%s",
        eval_model,
        bool(eval_platform_params),
        scenario.agent_id,
    )

    async def _generate_once() -> ResponseAccuracyResult:
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
            platform_config_raw=eval_platform_params,
            model=eval_model,
            agent_id=scenario.agent_id,
        )

        if not response.content:
            raise ValueError("No content returned by model")

        text_chunks = [c.text for c in response.content if isinstance(c, ResponseTextContent)]
        if not text_chunks:
            raise ValueError("No textual content returned by model")

        response_text = text_chunks[-1]
        logger.debug(f"Response accuracy response: {response_text}")

        parsed_result = parse_json_object(response_text)

        try:
            return ResponseAccuracyResult(**parsed_result)
        except TypeError as e:
            logger.debug(f"Parsed keys: {list(parsed_result.keys())}")
            raise ValueError("Parsed JSON does not match ResponseAccuracy schema") from e

    def _on_error(exc: BaseException, attempt: int) -> None:
        logger.warning(f"Evaluating Response Accuracy attempt {attempt} failed: {exc}")

    try:
        return await retry_async(_generate_once, on_error=_on_error)
    except RetryExceededError as exc:
        last_error = exc.last_error or exc.__cause__
        if last_error and is_rate_limit_error(last_error):
            error_message = log_and_format_error(
                log_message="Response Accuracy evaluation failed due to rate limits",
                user_message="Response Accuracy evaluation was rate limited.",
                error_code=ErrorCode.TOO_MANY_REQUESTS,
            )
        else:
            error_message = log_and_format_error(
                log_message="Response Accuracy could not be parsed after retries",
                user_message="Unexpected error: cannot evaluate response accuracy",
            )
        return ResponseAccuracyResult(passed=False, explanation=error_message, score=0)
