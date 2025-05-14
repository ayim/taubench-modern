import asyncio
from collections.abc import Callable, Coroutine
from contextlib import AsyncExitStack
from dataclasses import dataclass, field
from datetime import timedelta
from json import dumps
from typing import TYPE_CHECKING, Any

import httpx
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client

from agent_platform.core.configurations import Configuration, FieldMetadata
from agent_platform.core.tools.tool_definition import ToolDefinition

if TYPE_CHECKING:
    from agent_platform.core.mcp.mcp_server import MCPServer


@dataclass(frozen=True)
class MCPClientConfiguration(Configuration):
    read_timeout_seconds: int = field(
        default=30,
        metadata=FieldMetadata(
            description="The timeout for reading from the MCP server.",
            env_vars=["SEMA4AI_AGENT_SERVER_MCP_READ_TIMEOUT_SECONDS"],
        ),
    )


class MCPClient:
    """
    High-level client that automatically negotiates the transport (Streamable HTTP|SSE)
    and exposes a ready-to-use ``ClientSession`` instance.

    * MCP v1.8.0+ servers expose a single `/mcp` endpoint that accepts both POST and GET
      and may upgrade responses to SSE.
    * Older servers keep the two-endpoint HTTP+SSE design (`/sse` + `/sse/messages`).
    """

    def __init__(self, target_server: "MCPServer"):
        self.target_server = target_server

        self._exit_stack = AsyncExitStack()
        self._session: ClientSession | None = None
        self._get_session_id: Callable[[], str | None] | None = None

        self._connected = False
        self._connect_lock = asyncio.Lock()
        # Serialize in-flight tool calls to same server
        # (uncertain how well servers handle concurrent tool calls)
        self._call_lock = asyncio.Lock()

    # --------------------------------------------------------------------- #
    # Context-manager helpers                                               #
    # --------------------------------------------------------------------- #
    async def __aenter__(self) -> "MCPClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    # --------------------------------------------------------------------- #
    # Public properties                                                     #
    # --------------------------------------------------------------------- #
    @property
    def session(self) -> ClientSession:
        if not self._session:
            raise RuntimeError("MCP client not connected")
        return self._session

    @property
    def is_connected(self) -> bool:
        return self._connected and self._session is not None

    # --------------------------------------------------------------------- #
    # Connection/teardown logic                                             #
    # --------------------------------------------------------------------- #
    async def connect(self) -> None:
        """
        Try Streamable HTTP first; if *either* transport creation **or**
        `initialize()` fails, fall back to SSE.  Whole method is protected by
        `_connect_lock`, so concurrent coroutines will not race.
        """
        async with self._connect_lock:
            if self.is_connected:
                return

            base = self.target_server.url.rstrip("/")
            streamable_url = base if base.endswith("/mcp") else f"{base}/mcp"
            sse_url = base if base.endswith("/sse") else f"{base}/sse"

            # Fail fast: we should be able to do a GET to either of these endpoints
            # if we fail both, then we probably just have a bad URL or the server
            # isn't even running...
            any_url_works = False
            errors = {}
            async with httpx.AsyncClient() as client:

                async def check_url(url):
                    try:
                        await client.get(url)
                        return True
                    except httpx.RequestError as e:
                        errors[url] = e
                        return False

                results = await asyncio.gather(
                    check_url(streamable_url),
                    check_url(sse_url),
                    return_exceptions=False,
                )

                any_url_works = any(results)

            if not any_url_works:
                error_details = "; ".join(f"{url}: {errors[url]!s}" for url in errors)
                raise ConnectionError(
                    f"Failed to connect to MCP server {self.target_server.url}: "
                    f"no working transport found: {error_details}"
                )

            # Ordered list of (name, factory-callable, url)
            transports: list[tuple[str, Callable[[], Any]]] = [
                ("streamable", lambda: streamablehttp_client(streamable_url)),
                ("sse", lambda: sse_client(sse_url)),
            ]

            last_error: Exception | None = None

            for name, factory in transports:
                attempt_stack = AsyncExitStack()
                try:
                    # 1. open transport
                    streams = await attempt_stack.enter_async_context(factory())
                    if name == "streamable":
                        read_stream, write_stream, self._get_session_id = streams
                    else:  # SSE returns two items
                        read_stream, write_stream = streams

                    # 2. create a ClientSession and handshake
                    self._session = await attempt_stack.enter_async_context(
                        ClientSession(
                            read_stream,
                            write_stream,
                            read_timeout_seconds=timedelta(
                                seconds=MCPClientConfiguration.read_timeout_seconds,
                            ),
                        )
                    )
                    # TODO: In the case of timeouts... should we _not_ try again
                    # to avoid more latency... really we need to cache tool defs
                    # and only update when agent is updated (or via some manualy
                    # triggered refresh)
                    await self._session.initialize()  # may raise (bad handshake)

                except Exception as exc:
                    # transport failed --> clean up this attempt and try next
                    last_error = exc
                    await attempt_stack.aclose()
                    continue

                # success ---------------------------------------------------
                self._exit_stack = attempt_stack
                self._connected = True
                return

            # All transports failed
            raise ConnectionError(
                f"Failed to connect to MCP server {self.target_server.url}: "
                f"{last_error}",
            ) from last_error

    async def close(self) -> None:
        """Tear everything down; safe to call multiple times."""
        if not self.is_connected:
            return

        if self._exit_stack:
            await self._exit_stack.aclose()

        self._session = None
        self._exit_stack = None
        self._get_session_id = None
        self._connected = False

    # --------------------------------------------------------------------- #
    # Tool helpers                                                          #
    # --------------------------------------------------------------------- #
    async def list_tools(self) -> list[ToolDefinition]:
        """
        Fetch the tool catalogue and return a list of ``ToolDefinition`` objects
        whose ``function`` attribute is *already bound* to ``call_tool``.
        """
        if not self.is_connected:
            await self.connect()

        response = await self.session.list_tools()

        def _get_tool_function(
            tool_name: str,
        ) -> Callable[..., Coroutine[Any, Any, Any]]:
            async def _call_tool(**args: dict[str, Any]) -> Any:
                try:
                    # Lazy reconnect if the underlying transport was dropped.
                    if not self.is_connected:
                        await self.connect()

                    # Use the call lock to ensure only one call is processed at a time
                    async with self._call_lock:
                        # Execute the tool call
                        response = await self.session.call_tool(tool_name, args)
                        return response.model_dump_json()
                except Exception as e:
                    # Could enhance error handling with more specific error types
                    return dumps({"internal-error": str(e)})

            return _call_tool

        def _clean_input_schema(input_schema: dict[str, Any]) -> dict[str, Any]:
            return {
                k: v
                for k, v in (input_schema or {}).items()
                if k not in {"$schema", "additionalProperties"}
            }

        return [
            ToolDefinition(
                name=tool.name,
                description=tool.description or "",
                input_schema=_clean_input_schema(tool.inputSchema),
                function=_get_tool_function(tool.name),
            )
            for tool in response.tools
        ]
