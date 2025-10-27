from agent_platform.core.errors.responses import ErrorCode
from agent_platform.core.errors.streaming import StreamingError
from agent_platform.core.responses.streaming.stream_sink_noop import (
    NoOpResponseStreamSink,
)


class StopReasonGuardSink(NoOpResponseStreamSink):
    """Sink that raises immediately when a normalized stop reason indicates max tokens.

    Assumes providers set `message.stop_reason` to the canonical string "max_tokens".
    This sink is muted by the pipe after raising once; other sinks continue.
    """

    async def on_stop_reason(self, stop_reason: str | None) -> None:
        if stop_reason == "max_tokens":
            raise StreamingError(
                error_code=ErrorCode.PRECONDITION_FAILED,
                message="Model hit maximum output tokens during streaming.",
                data={"stop_reason": stop_reason},
            )
