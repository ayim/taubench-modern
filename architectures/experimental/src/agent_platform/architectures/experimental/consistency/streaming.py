import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Final

from tenacity import (
    AsyncRetrying,
    RetryCallState,
    before_sleep_log,
    retry_if_exception,
    stop_after_attempt,
    wait_random_exponential,
)

from agent_platform.architectures.experimental.checkpoint import (
    CheckpointTxn,
    is_transient_stream_error,
)
from agent_platform.architectures.experimental.consistency.state import ConsistencyArchState
from agent_platform.core.kernel_interfaces.model_platform import PlatformInterface
from agent_platform.core.kernel_interfaces.thread_state import ThreadMessageWithThreadState
from agent_platform.core.prompts.prompt import Prompt
from agent_platform.core.responses.streaming.stream_pipe import ResponseStreamPipe

# Signature for a function that wires a ResponseStreamPipe into sinks.
PipeFn = Callable[
    [ResponseStreamPipe, ThreadMessageWithThreadState, ConsistencyArchState],
    Awaitable[None],
]


@dataclass(frozen=True, slots=True)
class PipeSpec:
    """Identifies a streaming call flavor and how to pipe its chunks into sinks."""

    call_type: str
    pipe_fn: PipeFn


async def _tool_loop_pipe(
    stream: ResponseStreamPipe,
    message: ThreadMessageWithThreadState,
    state: ConsistencyArchState,
) -> None:
    """Pipe chunks for a tool-loop call into the appropriate sinks."""
    await stream.pipe_to(
        message.sinks.stop_reason_guard,
        message.sinks.reasoning,
        message.sinks.tool_calls(),
        message.sinks.usage,
        state.sinks.pending_tool_calls,
    )


async def _final_reply_pipe(
    stream: ResponseStreamPipe,
    message: ThreadMessageWithThreadState,
    state: ConsistencyArchState,
) -> None:
    """Pipe chunks for a final-reply call into the appropriate sinks."""
    await stream.pipe_to(
        message.sinks.stop_reason_guard,
        message.sinks.reasoning,
        message.sinks.raw_content,
        message.sinks.usage,
    )


PIPE_TOOL_LOOP: Final[PipeSpec] = PipeSpec(call_type="tool-loop", pipe_fn=_tool_loop_pipe)
PIPE_FINAL_REPLY: Final[PipeSpec] = PipeSpec(call_type="final-reply", pipe_fn=_final_reply_pipe)

# Retry knobs tuned for possibly flaky SSE streams across major providers.
RETRY_ATTEMPTS: Final[int] = 4
WAIT_STRATEGY = wait_random_exponential(
    multiplier=0.5,
    min=0.5,
    max=3.0,
)

logger = logging.getLogger(__name__)


async def stream_with_retry(
    platform: PlatformInterface,
    model: str,
    prompt: Prompt,
    message: ThreadMessageWithThreadState,
    state: ConsistencyArchState,
    spec: PipeSpec,
) -> ResponseStreamPipe:
    """
    Stream a model response with retries on transient mid-stream errors (e.g., broken SSE).

    Behavior:
      - Marks prompt start before the first attempt.
      - Each attempt opens a streaming context and pipes chunks via `spec.pipe_fn`.
      - Transient failures roll back the checkpoint and are retried (initial + 3 retries).
      - On terminal success: commits checkpoint, marks prompt end, records usage metadata.
      - On terminal failure: logs with stack trace, marks prompt end, and re-raises.

    Returns:
        The completed ResponseStreamPipe (with `reassembled_response` populated).
    """
    import asyncio

    message.mark_prompt_start()

    def _log_attempt(retry_state: RetryCallState) -> None:
        logger.info(
            "Streaming %s on %s/%s (attempt %d/%d)",
            spec.call_type,
            platform.name,
            model,
            retry_state.attempt_number,
            RETRY_ATTEMPTS,
        )

    async for attempt in AsyncRetrying(
        retry=retry_if_exception(is_transient_stream_error),
        stop=stop_after_attempt(RETRY_ATTEMPTS),
        wait=WAIT_STRATEGY,
        reraise=True,
        before=_log_attempt,
        before_sleep=before_sleep_log(logger, logging.WARNING),
    ):
        with attempt:
            ckpt = CheckpointTxn(message, state)
            try:
                async with platform.stream_response(prompt, model) as stream:
                    await spec.pipe_fn(stream, message, state)
            except BaseException as exc:  # handle cancellations distinctly; still rollback
                await ckpt.rollback()

                # Do not retry cancellations; surface immediately without spurious error logs.
                if isinstance(exc, (KeyboardInterrupt | asyncio.CancelledError)):
                    message.mark_prompt_end()
                    raise

                # If Tenacity won't retry, this is terminal; add stack trace and end timing.
                should_retry = is_transient_stream_error(exc) and attempt.retry_state.attempt_number < RETRY_ATTEMPTS
                if not should_retry:
                    logger.error(
                        "%s stream failed on %s/%s: %s",
                        spec.call_type,
                        platform.name,
                        model,
                        exc,
                        exc_info=True,
                    )
                    message.mark_prompt_end()
                raise

            # Success path: persist and record usage.
            ckpt.commit()
            message.mark_prompt_end()
            message.update_usage_metadata(
                platform=platform.name,
                model=model,
                call_type=spec.call_type,
                response=stream.reassembled_response,
            )
            return stream

    raise RuntimeError("Unreachable code path")
