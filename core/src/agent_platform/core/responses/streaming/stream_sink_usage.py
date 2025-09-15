from collections.abc import Awaitable, Callable

from agent_platform.core.responses.response import TokenUsage
from agent_platform.core.responses.streaming.stream_sink_noop import (
    NoOpResponseStreamSink,
)


async def _on_usage_received_noop(
    usage: TokenUsage,
) -> None:
    """A no-op on_usage_received callback."""
    pass


class UsageResponseStreamSink(NoOpResponseStreamSink):
    """
    This stream sink will call:

    - on_usage_received()       : whenever we first see a new usage content
    """

    def __init__(
        self,
        on_usage_received: Callable[
            [TokenUsage],
            Awaitable[None],
        ] = _on_usage_received_noop,
    ):
        self.on_usage_received = on_usage_received

    async def on_usage(
        self,
        usage: TokenUsage,
    ) -> None:
        await self.on_usage_received(usage)
