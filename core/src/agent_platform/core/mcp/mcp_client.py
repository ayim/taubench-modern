import asyncio
from collections.abc import Callable, Coroutine
from contextlib import AsyncExitStack
from json import dumps
from typing import TYPE_CHECKING, Any

from mcp import ClientSession
from mcp.client.sse import sse_client

from agent_platform.core.tools.tool_definition import ToolDefinition

if TYPE_CHECKING:
    from agent_platform.core.mcp.mcp_server import MCPServer


class MCPClient:
    def __init__(self, target_server: "MCPServer"):
        self.target_server = target_server
        self._session: ClientSession | None = None
        self._exit_stack = AsyncExitStack()
        self._connected = False
        self._connect_lock = asyncio.Lock()
        self._call_lock = asyncio.Lock()

    async def __aenter__(self) -> "MCPClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    @property
    def session(self) -> ClientSession:
        if not self._session:
            raise RuntimeError("MCP client not connected")
        return self._session

    @property
    def is_connected(self) -> bool:
        return self._connected and self._session is not None

    async def connect(self) -> None:
        """
        Opens an SSE client connection to the remote MCP server, creates
        a ClientSession, and initializes it.
        """
        async with self._connect_lock:
            if self.is_connected:
                return

            try:
                # TODO: headers?
                headers = {}

                # Open the SSE-based transport within our async context manager
                sse_transport = await self._exit_stack.enter_async_context(
                    sse_client(
                        url=self.target_server.url,
                        headers=headers or None,
                    ),
                )

                # Create the MCP ClientSession using the read/write from SSE transport
                self._session = await self._exit_stack.enter_async_context(
                    ClientSession(
                        read_stream=sse_transport[0],
                        write_stream=sse_transport[1],
                    ),
                )

                # Initialize session (MCP handshake, listing tools, etc.)
                await self._session.initialize()
                self._connected = True
            except Exception as e:
                # If anything fails during connection setup, ensure we clean up properly
                await self._exit_stack.aclose()
                self._session = None
                self._connected = False
                raise ConnectionError(f"Failed to connect to MCP server: {e!s}") from e

    async def close(self) -> None:
        """
        Closes the MCP client session.
        """
        if not self.is_connected:
            return

        try:
            await self._exit_stack.aclose()
        except Exception as e:
            # Log the error but don't re-raise to ensure cleanup continues
            print(f"Error during MCP client close: {e!s}")
        finally:
            self._session = None
            self._connected = False

    async def list_tools(self) -> list[ToolDefinition]:
        """
        Lists the tools available on the MCP server.
        """
        if not self.is_connected:
            await self.connect()

        if not self._session:
            raise RuntimeError("MCP client not connected")

        response = await self._session.list_tools()

        def _get_tool_function(
            tool_name: str,
        ) -> Callable[..., Coroutine[Any, Any, Any]]:
            async def _call_tool(**args: dict[str, Any]) -> Any:
                try:
                    # Ensure we have a valid connection
                    if not self.is_connected:
                        await self.connect()

                    if not self._session:
                        raise RuntimeError("MCP client not connected")

                    # Use the call lock to ensure only one call is processed at a time
                    async with self._call_lock:
                        # Execute the tool call
                        response = await self._session.call_tool(tool_name, args)
                        return response.model_dump_json()
                except Exception as e:
                    # Could enhance error handling with more specific error types
                    return dumps({"internal-error": str(e)})

            return _call_tool

        def _clean_input_schema(input_schema: dict[str, Any]) -> dict[str, Any]:
            return {
                k: v
                for k, v in input_schema.items()
                if k not in ["$schema", "additionalProperties"]
            }

        return [
            ToolDefinition(
                name=tool.name,
                description=tool.description or "",
                input_schema=_clean_input_schema(tool.inputSchema or {}),
                function=_get_tool_function(tool.name),
            )
            for tool in response.tools
        ]
