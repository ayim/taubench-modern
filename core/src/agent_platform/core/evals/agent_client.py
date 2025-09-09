from abc import abstractmethod
from dataclasses import dataclass
from datetime import UTC, datetime

import structlog

from agent_platform.core.delta.base import GenericDelta
from agent_platform.core.delta.combine_delta import combine_generic_deltas
from agent_platform.core.evals.session import Session
from agent_platform.core.streaming.delta import (
    StreamingDelta,
    StreamingDeltaMessageBegin,
    StreamingDeltaMessageContent,
    StreamingDeltaRequestToolExecution,
)
from agent_platform.core.streaming.incoming import IncomingDeltaClientToolResult
from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.messages import ThreadAgentMessage

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class Tool:
    tool_call_id: str
    tool_name: str
    input_raw: str


@dataclass(frozen=True)
class ToolExecutionResult:
    output: str
    error: str | None


class ToolExecutor:
    @abstractmethod
    async def execute(self, tool: Tool) -> ToolExecutionResult:
        raise NotImplementedError("Not implemented yet")


class AgentClient:
    def __init__(self, tool_executor: ToolExecutor, session: Session):
        self.tool_executor = tool_executor
        self.session = session

        self._message_chunks: list[list[GenericDelta]] = []

    async def run_once(self) -> list[ThreadMessage]:
        async with self.session:
            async for event in self.session:
                await self._handle_event(event)

        return self.get_messages()

    def get_messages(self) -> list[ThreadMessage]:
        # TODO cache this result
        return [
            ThreadAgentMessage.model_validate(combine_generic_deltas(chunk))
            for chunk in self._message_chunks
        ]

    async def _handle_event(self, event: StreamingDelta) -> None:
        if isinstance(event, StreamingDeltaMessageBegin):
            self._message_chunks.append([])
        elif isinstance(event, StreamingDeltaMessageContent):
            self._message_chunks[-1].append(event.delta)
        elif isinstance(event, StreamingDeltaRequestToolExecution):
            try:
                logger.info(f"Executing tool {event.tool_name}")
                execute_result = await self.tool_executor.execute(
                    Tool(
                        tool_call_id=event.tool_call_id,
                        tool_name=event.tool_name,
                        input_raw=event.input_raw,
                    )
                )
                incoming_event = IncomingDeltaClientToolResult(
                    result={"output": execute_result.output, "error": execute_result.error},
                    timestamp=datetime.now(UTC),
                    tool_call_id=event.tool_call_id,
                )
                logger.info(f"Tool {event.tool_name} executed successfully")
                await self.session.send(incoming_event)
            except Exception as e:
                logger.error(f"Error Executing tool {event.tool_name}: {e}")
                raise
