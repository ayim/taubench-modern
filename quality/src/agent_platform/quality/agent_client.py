import asyncio
import json
import sys
from abc import abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog

from agent_platform.quality.agent_runner import (
    build_agent_platform_message,
    from_api_response_to_messages,
)
from agent_platform.quality.delta import apply_delta
from agent_platform.quality.models import Message
from agent_platform.quality.utils import safe_join_url
from agent_platform.quality.websocket import WebSocketClient

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class Tool:
    tool_call_id: str
    tool_name: str
    input_raw: str


@dataclass(frozen=True)
class ClientTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    category: str = "client-exec-tool"


@dataclass(frozen=True)
class ToolExecutionResult:
    output: str
    error: str | None


class ToolExecutor:
    @abstractmethod
    async def execute(self, tool: Tool) -> ToolExecutionResult:
        raise NotImplementedError("Not implemented yet")


class AgentClient:
    def __init__(
        self,
        thread_name: str,
        agent_id: str,
        agent_server_base_url: str,
        tools: list[ClientTool],
        tool_executor: ToolExecutor,
    ):
        self.thread_name = thread_name
        self.agent_id = agent_id
        self.tools = tools
        self.tool_executor = tool_executor
        self._messages: dict[str, dict[str, Any]] = {}
        self._finished: asyncio.Future[None] = asyncio.get_event_loop().create_future()
        self.agent_server_base_url = agent_server_base_url

        ws_url = safe_join_url(agent_server_base_url, f"/api/v2/runs/{agent_id}/stream").replace("http", "ws", 1)
        self._client = WebSocketClient(url=ws_url, on_message=self._handle_event)

        self._handlers: dict[str, Callable[[dict[str, Any]], Awaitable[None]]] = {
            "agent_ready": self._on_agent_ready,
            "agent_finished": self._on_agent_finished,
            "message_begin": self._on_message_begin,
            "message_end": self._on_message_end,
            "message_content": self._on_message_content,
            "request_tool_execution": self._on_request_tool_execution,
        }

    async def run_once(self, messages: list[Message]) -> list[Message]:
        async with self._client:
            payload = self._build_initial_payload(messages)
            await self._client.send_json(payload)
            await self._wait_finished(timeout=120)
        return from_api_response_to_messages(list(self._messages.values()))

    def get_messages(self) -> list[Message]:
        return from_api_response_to_messages(list(self._messages.values()))

    async def _handle_event(self, event: dict[str, Any]) -> None:
        etype = event.get("event_type", "")
        handler = self._handlers.get(etype, self._on_unknown_event)
        await handler(event)

    async def _on_agent_ready(self, _: dict[str, Any]) -> None:
        return

    async def _on_agent_finished(self, _: dict[str, Any]) -> None:
        if not self._finished.done():
            self._finished.set_result(None)

    async def _on_message_begin(self, event: dict[str, Any]) -> None:
        mid = event["message_id"]
        self._messages[mid] = {
            "message_id": mid,
            "thread_id": event.get("thread_id"),
            "agent_id": event.get("agent_id"),
            "content": [],
            "complete": False,
            "committed": False,
        }

    async def _on_message_end(self, event: dict[str, Any]) -> None:
        mid = event["message_id"]
        snapshot = event.get("data") or {}
        if mid in self._messages:
            self._messages[mid].update(snapshot)
        else:
            self._messages[mid] = snapshot

    async def _on_message_content(self, event: dict[str, Any]) -> None:
        mid = event["message_id"]
        self._messages.setdefault(mid, {"message_id": mid, "content": []})
        delta = event.get("delta") or {}
        try:
            apply_delta(self._messages[mid], delta)
        except Exception as e:
            logger.error(f"[patch error] {e} for delta={delta}", file=sys.stderr)

    async def _on_request_tool_execution(self, event: dict[str, Any]) -> None:
        tool_call_id = event.get("tool_call_id")
        tool_name = event.get("tool_name")
        input_raw = event.get("input_raw")

        if tool_name is None:
            raise RuntimeError("tool_name is null")

        if tool_call_id is None:
            raise RuntimeError("tool_call_id is null")

        if input_raw is None:
            raise RuntimeError("input_raw is null")

        try:
            logger.info(f"Executing tool {tool_name}")
            execute_result = await self.tool_executor.execute(
                Tool(tool_call_id=tool_call_id, tool_name=tool_name, input_raw=input_raw)
            )
            payload = {
                "event_type": "client_tool_result",
                "timestamp": datetime.now(UTC).isoformat(),
                "tool_call_id": tool_call_id,
                "result": {"output": execute_result.output, "error": execute_result.error},
            }
            await self._client.send_json(payload)
        except Exception as e:
            if not self._finished.done():
                self._finished.set_exception(e)

    async def _on_unknown_event(self, event: dict[str, Any]) -> None:
        logger.error(f"[unknown] {json.dumps(event, ensure_ascii=False)}")

    async def _wait_finished(self, timeout: float | None = None) -> None:
        try:
            await asyncio.wait_for(self._finished, timeout=timeout)
        except TimeoutError:
            logger.error("[agent] timed out waiting for finish", file=sys.stderr)

    def _build_initial_payload(self, messages: list[Message]) -> dict[str, Any]:
        return {
            "name": self.thread_name,
            "agent_id": self.agent_id,
            "client_tools": [tool.__dict__ for tool in self.tools],
            "messages": [build_agent_platform_message(message) for message in messages],
            "metadata": {},
        }
