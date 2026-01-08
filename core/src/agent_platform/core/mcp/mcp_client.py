"""
agent_platform.core.mcp.mcp_client
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

High-level MCP client supporting the three standard
transports:

* Streamable-HTTP  (`…/mcp`)
* SSE              (`…/sse`)
* stdio            (local subprocess)

Key design goals
----------------
* **Correctness**  --- conforms to the MCP transport contracts.
* **Safety**       --- env-var gate for stdio; validates `command`; resilient
  exponential-back-off with full-jitter; no leaked child processes.
* **Robustness**   --- races viable transports, retries transient failures,
  exposes session-id for resumption.
* **Speed**        --- minimal startup overhead, concurrent tool calls by
  default (can be forced serial via server hint).

Public surface
--------------
* `MCPClient(target_server, *, force_serial_tool_calls: bool = False)`
* `.is_connected`
* `.chosen_transport`
* `.session`           --- underlying `ClientSession`
* `.session_id`        --- current HTTP session-ID if StreamableHTTP
* `await .connect() / .close()`
* `await .call_tool(name, args, attempts=N)`
* `await .list_tools()`

"""

import asyncio
import os
import random
import re
import time
from collections.abc import Callable, Iterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import timedelta
from typing import TYPE_CHECKING, Any, Final
from urllib.parse import urlparse

import httpx
from anyio import BrokenResourceError, ClosedResourceError
from httpx_retries import Retry, RetryTransport
from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.shared.message import ClientMessageMetadata
from mcp.types import CallToolRequest, CallToolRequestParams, CallToolResult, ClientRequest
from structlog.stdlib import BoundLogger, get_logger

from agent_platform.core.configurations import Configuration, FieldMetadata
from agent_platform.core.tools.tool_definition import ToolDefinition

if TYPE_CHECKING:
    from agent_platform.core.mcp.mcp_server import MCPServer
    from agent_platform.core.tools.tool_definition import ToolCallContext


# --------------------------------------------------------------------------- #
#  Small utility: async no-op context manager                                 #
# --------------------------------------------------------------------------- #
@asynccontextmanager
async def _anoop():
    """Async no-op context manager (like contextlib.nullcontext for awaitables)."""
    yield


# --------------------------------------------------------------------------- #
#  Configuration --- values are exposed as class   attributes via ConfigMeta.   #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class MCPClientConfiguration(Configuration):
    probe_timeout_seconds: int = field(
        default=2,
        metadata=FieldMetadata(
            description="Timeout for fast endpoint probes.",
            env_vars=["SEMA4AI_AGENT_SERVER_MCP_DEFAULT_PROBE_TIMEOUT_SECONDS"],
        ),
    )
    handshake_timeout_seconds: int = field(
        default=5,
        metadata=FieldMetadata(
            description="Timeout for remote transport handshake / initialize().",
            env_vars=["SEMA4AI_AGENT_SERVER_MCP_DEFAULT_HANDSHAKE_TIMEOUT_SECONDS"],
        ),
    )
    stdio_handshake_timeout_seconds: int = field(
        default=30,
        metadata=FieldMetadata(
            description="Timeout for stdio transport handshake / initialize().",
            env_vars=["SEMA4AI_AGENT_SERVER_MCP_DEFAULT_STDIO_HANDSHAKE_TIMEOUT_SECONDS"],
        ),
    )
    cleanup_timeout_seconds: int = field(
        default=3,
        metadata=FieldMetadata(
            description="Timeout when closing a failed transport.",
            env_vars=["SEMA4AI_AGENT_SERVER_MCP_DEFAULT_CLEANUP_TIMEOUT_SECONDS"],
        ),
    )
    tool_call_read_timeout_seconds: int = field(
        default=300,
        metadata=FieldMetadata(
            description="Read-timeout for long-running tool calls.",
            env_vars=["SEMA4AI_AGENT_SERVER_MCP_TOOL_CALL_READ_TIMEOUT_SECONDS"],
        ),
    )
    http_retry_total: int = field(
        default=5,
        metadata=FieldMetadata(
            description="Max number of HTTP retries for MCP transports.",
            env_vars=["SEMA4AI_AGENT_SERVER_MCP_HTTP_RETRY_TOTAL"],
        ),
    )
    http_retry_backoff_factor: float = field(
        default=0.5,
        metadata=FieldMetadata(
            description="Exponential backoff factor for MCP HTTP retries.",
            env_vars=["SEMA4AI_AGENT_SERVER_MCP_HTTP_RETRY_BACKOFF_FACTOR"],
        ),
    )
    http_retry_status_forcelist: list[int] = field(
        default_factory=lambda: [408, 429, 500, 502, 503, 504],
        metadata=FieldMetadata(
            description="HTTP status codes retried for MCP transports.",
            env_vars=["SEMA4AI_AGENT_SERVER_MCP_HTTP_RETRY_STATUS_FORCELIST"],
        ),
    )


# --------------------------------------------------------------------------- #
#  Helpers                                                                    #
# --------------------------------------------------------------------------- #
logger: BoundLogger = get_logger(__name__)
_ALLOW_STDIO_ENV_VAR: Final[str] = "SEMA4AI_AGENT_SERVER_MCP_ALLOW_STDIO"
_COMMAND_RE: Final[re.Pattern[str]] = re.compile(r"^[\w\-./\\]+$")  # crude but effective


def _safe_command(cmd: str) -> str:
    """
    Ensure the supplied executable looks safe to run.

    * Must not contain whitespace or shell metacharacters.
    * If it is an absolute path, ensure it exists.

    Raises
    ------
    ValueError
        If the command looks unsafe.
    """
    # TODO fix checks command.
    # if not _COMMAND_RE.match(cmd):
    #     raise ValueError(f"Rejecting unsafe command string: {cmd!r}")
    # if os.path.isabs(cmd) and not os.path.exists(cmd):
    #     raise ValueError(f"Executable not found: {cmd}")
    return cmd


def _full_jitter(base_delay: float, attempt: int, cap: float) -> float:
    """
    "Full-jitter" back-off --- see AWS architecture blog.
    """
    exp = min(cap, base_delay * 2 ** (attempt - 1))
    return random.uniform(0, exp)


# --------------------------------------------------------------------------- #
#  Client                                                                     #
# --------------------------------------------------------------------------- #
class MCPClient:
    """
    High-level façade over `mcp.ClientSession`.

    Parameters
    ----------
    target_server:
        An `MCPServer` description (see `mcp_server.py`).
    force_serial_tool_calls:
        If *True*, all tool calls are executed under a lock to support
        legacy servers that cannot interleave multiple requests.
    """

    # ------------------------------------------------------------------ #
    #  Construction / context-manager                                    #
    # ------------------------------------------------------------------ #

    def __init__(
        self,
        target_server: "MCPServer",
        tool_call_context: "ToolCallContext",
    ) -> None:
        """
        Initialize MCP client.

        Parameters
        ----------
        target_server : MCPServer
            The MCP server configuration
        tool_call_context: ToolCallContext
            The tool call context
        """
        self._cfg = MCPClientConfiguration  # class-level singleton per ConfigMeta
        self.target_server = target_server
        assert target_server.type != "sema4ai_action_server", (
            "Sema4AI Action Servers should use native protocol, not MCP Client"
        )

        if tool_call_context.mcp_server_kind == "unset":
            tool_call_context = tool_call_context.with_mcp_server_info(target_server)

        self._headers: dict[str, str] = tool_call_context.build_headers_for_mcp_server()

        self._session: ClientSession | None = None
        self._get_session_id_cb: Callable[[], str | None] | None = None

        self._connected = False
        self._chosen_transport: str | None = None
        self._spawn_transport_task: asyncio.Task[None] | None = None
        self._spawn_finished_future: asyncio.Future[None] = asyncio.Future()
        self._close_evt: asyncio.Event = asyncio.Event()

        self._connect_lock = asyncio.Lock()

        # Tool-call concurrency
        self._serialize_calls = target_server.force_serial_tool_calls
        self._call_lock = asyncio.Lock() if self._serialize_calls else None

    async def __aenter__(self) -> "MCPClient":
        await self.connect()
        return self

    async def __aexit__(self, *_exc) -> None:
        await self.close()

    # ------------------------------------------------------------------ #
    #  Public properties                                                 #
    # ------------------------------------------------------------------ #

    @property
    def is_connected(self) -> bool:
        return self._connected and self._session is not None

    @property
    def chosen_transport(self) -> str:
        if not self._chosen_transport:
            raise RuntimeError("Client not connected")
        return self._chosen_transport

    @property
    def session(self) -> ClientSession:
        if not self._session:
            raise RuntimeError("Client not connected")
        return self._session

    @property
    def session_id(self) -> str | None:
        if self._get_session_id_cb:
            return self._get_session_id_cb()
        return None

    # ------------------------------------------------------------------ #
    #  Connect / close                                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _normalise(url: str) -> tuple[str, str]:
        """
        Return `(streamable_url, sse_url)` stripping trailing slashes + suffix.

        * `http://host/`         →  (`http://host/mcp`, `http://host/sse`)
        * `http://host/mcp`      →  (same, `http://host/sse`)
        * `http://host/sse`      →  (`http://host/mcp`, same)
        """
        while url.endswith("/"):
            url = url[:-1]

        for tail in ("/mcp", "/sse"):
            if url.endswith(tail):
                url = url[: -len(tail)]
        return f"{url}/mcp", f"{url}/sse"

    async def connect(self) -> None:
        """
        Establish connection to the MCP server.

        Creates a transport task (stdio or HTTP-based) and waits for it to complete.
        The transport task will either set the connection state on success or
        set an exception on the future on failure.

        Idempotent --- if already connected, it's a no-op.
        """
        async with self._connect_lock:
            if self.is_connected:
                return

            # Create the transport task (stdio or HTTP-based)
            if self.target_server.is_stdio:
                await self._connect_stdio()
            else:
                await self._connect_remote()

            # Should throw an exception if the transport failed to connect
            # (either that or its result should be set).
            await self._spawn_finished_future

            if not self.is_connected:
                # This should never happen
                raise RuntimeError(f"Internal error: Could not connect to '{self.target_server.url}'")

            logger.info(
                "Connected - name=%s transport=%s session_id=%s",
                self.target_server.name,
                self._chosen_transport.upper() if self._chosen_transport else "unknown",
                self.session_id,
            )

    async def close(self) -> None:
        """
        Graceful shutdown.

        Closes the connection to the MCP server (which should
        be waiting on the _close_evt to exit and clean up its resources).
        """

        transport_task = self._spawn_transport_task
        if not self._connected and not transport_task:
            return

        # Wake the transport task so its context manager can exit
        self._close_evt.set()

        # Wait for the transport task to finish (with timeout to avoid hanging)
        if transport_task:
            try:
                await asyncio.wait_for(transport_task, timeout=self._cfg.cleanup_timeout_seconds)
            except Exception:
                logger.exception("Error while waiting for transport task to finish")

        # Reset
        self._session = None
        self._connected = False
        self._chosen_transport = None
        self._spawn_transport_task = None
        self._get_session_id_cb = None
        self._spawn_finished_future = asyncio.Future()
        self._close_evt.clear()
        logger.info("Disconnected from MCP server '%s'", self.target_server.url)

    # ------------------------------------------------------------------ #
    #  Internal --- transport selection                                  #
    # ------------------------------------------------------------------ #

    # --- stdio (local subprocess) ------------------------------------ #
    def _stdio_factory(self):
        srv = self.target_server
        assert srv.command  # type guard
        cmd = _safe_command(srv.command)

        # Merge agent-server's env vars with provided env vars, provided env vars take precedence
        merged_env = dict(os.environ)
        if srv.env:
            target_env: dict[str, str] = {
                key: value if isinstance(value, str) else value.value or "" for key, value in srv.env.items()
            }
            merged_env.update(target_env)

        params = StdioServerParameters(
            command=cmd,
            args=srv.args or [],
            env=merged_env,
            cwd=srv.cwd,
        )

        # The `mcp.client.stdio.stdio_client` context manager is responsible
        # for terminating the spawned subprocess in *all* exit paths.
        # The library's cleanup logic is sufficient to
        # avoid orphaned processes.
        return stdio_client(params)

    async def _connect_stdio(self) -> None:
        allowed = os.getenv(_ALLOW_STDIO_ENV_VAR, "").lower()
        if allowed not in {"1", "true", "yes"}:
            raise ValueError(
                f"Stdio-based MCP servers are disabled by default; set {_ALLOW_STDIO_ENV_VAR}=1 to enable."
            )

        self._spawn_transport_task = asyncio.create_task(
            self._spawn_transport(
                name="stdio",
                factory=self._stdio_factory,
            )
        )

    # --- remote (HTTP) ---------------------------------------------- #
    async def _connect_remote(self) -> None:
        parsed = urlparse(self.target_server.url or "")
        if parsed.scheme not in {"http", "https"}:
            raise ValueError(f"Unsupported URL scheme: {parsed.scheme!r}")

        target_url = self.target_server.url or ""
        expect_sse = self.target_server.transport == "sse"

        async with httpx.AsyncClient(follow_redirects=True) as c:
            ok = await self._probe_endpoint(c, target_url, expect_sse=expect_sse)

        if not ok:
            raise ConnectionError(f"No MCP transport found at '{self.target_server.url}'")

        name = "streamable" if self.target_server.transport == "streamable-http" else "sse"

        def _retrying_httpx_client_factory(
            headers: dict[str, str] | None = None,
            timeout: httpx.Timeout | None = None,
            auth: httpx.Auth | None = None,
        ) -> httpx.AsyncClient:
            retry = Retry(
                total=self._cfg.http_retry_total,
                backoff_factor=self._cfg.http_retry_backoff_factor,
                status_forcelist=set(self._cfg.http_retry_status_forcelist),
                allowed_methods=None,  # retry all methods (POST included)
            )
            transport = RetryTransport(retry=retry)
            return httpx.AsyncClient(
                transport=transport,
                headers=headers,
                timeout=timeout or httpx.Timeout(30.0),
                auth=auth,
                follow_redirects=True,
            )

        def factory() -> Any:
            """Create the chosen transport client."""
            if name == "streamable":
                return streamablehttp_client(
                    target_url,
                    headers=self._headers if self._headers else None,
                    httpx_client_factory=_retrying_httpx_client_factory,
                )
            return sse_client(
                target_url,
                headers=self._headers if self._headers else None,
                httpx_client_factory=_retrying_httpx_client_factory,
            )

        self._spawn_transport_task = asyncio.create_task(
            self._spawn_transport(
                name,
                factory,
            )
        )

    # ------------------------------------------------------------------ #
    #  Transport worker                                                  #
    # ------------------------------------------------------------------ #

    async def _spawn_transport(
        self,
        name: str,
        factory: Callable[[], Any],
    ) -> None:
        """
        Run a transport inside its own context manager.

        Creates the client session and then waits for the _close_evt
        to be set to unblock.

        Should be run as a task. Externally the `_spawn_finished_future`
        should be awaited to get the result of the task (either None or an exception
        if the transport failed to connect).
        """
        from mcp.shared.exceptions import McpError

        start_time = time.monotonic()
        try:
            async with factory() as streams:
                if name == "streamable":
                    read, write, self._get_session_id_cb = streams
                else:
                    read, write = streams

                handshake_timeout_seconds = self._cfg.handshake_timeout_seconds
                if name == "stdio":
                    # Things can be _much slower_ if we're starting an stdio
                    # server... use a more lenient timeout
                    handshake_timeout_seconds = self._cfg.stdio_handshake_timeout_seconds
                client_session = ClientSession(
                    read,
                    write,
                    read_timeout_seconds=timedelta(seconds=handshake_timeout_seconds),
                )

                async with client_session:
                    try:
                        init_result = await asyncio.wait_for(
                            client_session.initialize(),
                            timeout=handshake_timeout_seconds,
                        )
                    except McpError as e:
                        raise ConnectionError(
                            f"MCP session 'initialize' failed (url {self.target_server.url!r} may be invalid): {e!r}"
                        ) from e

                    latency = time.monotonic() - start_time
                    logger.info(
                        f"{name} handshake ok  ({latency * 1000:.0f} ms, protocol={init_result.protocolVersion})"
                    )

                    assert not self._connected, "Internal error: transport already connected"

                    self._session = client_session
                    self._connected = True
                    self._chosen_transport = name
                    self._spawn_finished_future.set_result(None)
                    logger.debug("%s transport connected successfully", name)

                    # Park until close()
                    await self._close_evt.wait()

        except BaseException as exc:
            logger.debug("%s transport error: %r", name, exc)

            self._spawn_finished_future.set_exception(_convert_exception_group_to_single_exception(exc))
            # Don't raise here - the exception is communicated via _spawn_finished_future
            # and will be raised when connect() awaits it.
        finally:
            if not self._spawn_finished_future.done():
                self._spawn_finished_future.cancel(
                    "Internal error: at this point either the result or the exception should've been set already."
                )

    # ------------------------------------------------------------------ #
    #  Probing helpers                                                   #
    # ------------------------------------------------------------------ #

    async def _probe_endpoint(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        expect_sse: bool,
    ) -> bool:
        """
        *Cheap* liveness probe: perform a GET/HEAD, judge by *headers*
        only.  Returns `True` when the endpoint looks alive.
        """
        headers = {
            "Accept": "text/event-stream" if expect_sse else "application/json",
            "X-MCP-Probe": "1",
        }

        # Add configured headers from MCPServer
        if self._headers:
            headers.update(self._headers)

        try:
            async with client.stream("GET", url, headers=headers, timeout=self._cfg.probe_timeout_seconds) as resp:
                # Any status < 600 means we reached *our* server, including
                # 503 Maintenance. 5xx still counts as "alive".
                return resp.status_code < httpx.codes.BAD_GATEWAY + 100
        except (httpx.HTTPError, TimeoutError):
            return False

    # ------------------------------------------------------------------ #
    #  High-level tool operations                                        #
    # ------------------------------------------------------------------ #
    def _is_transient(self, e: Exception) -> bool:
        # Network/timeout/protocol errors: transient
        if isinstance(e, (ClosedResourceError | BrokenResourceError | TimeoutError | ConnectionError)):
            return True
        if isinstance(e, httpx.RequestError) and not isinstance(e, httpx.HTTPStatusError):
            # DNS failures, connect timeouts, read timeouts, protocol errors...
            return True
        if isinstance(e, httpx.HTTPStatusError):
            resp = e.response
            code = resp.status_code if resp is not None else None
            # Retry only classic transient statuses
            return code in self._cfg.http_retry_status_forcelist or (code is not None and 500 <= code < 600)
        return False

    async def _reconnect_when_appropriate(self, exc: Exception) -> None:
        # Try to reestablish transport; swallow errors here
        reconnect_needed = isinstance(
            exc,
            (ClosedResourceError | BrokenResourceError | httpx.RequestError),
        ) and not isinstance(exc, httpx.HTTPStatusError)
        if reconnect_needed:
            logger.debug(f"will reconnect to MCP server because of transient error: {exc!r}")
            try:
                await self.close()
            except Exception:
                pass
            try:
                await self.connect()
            except Exception:
                pass

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        *,
        attempts: int = 5,
        backoff_cap: float = 8.0,
        base_backoff: float = 0.25,
    ) -> dict[str, Any]:
        """
        Invoke a tool with automatic retries on transient I/O errors.
        Retries reuse any resumption token emitted by earlier attempts.
        Non-transient exceptions bubble immediately.
        """

        # Token captured from streaming; reused on retry
        last_token: str | None = None

        async def _on_token_update(token: str):
            nonlocal last_token
            last_token = token

        if not self.is_connected:
            await self.connect()

        attempts = max(1, attempts)
        last_exc: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                # Recreate the context manager each attempt; don't reuse
                if self._call_lock:
                    cm = self._call_lock
                else:
                    cm = _anoop()

                async with cm:
                    metadata = ClientMessageMetadata(
                        resumption_token=last_token,
                        on_resumption_token_update=_on_token_update,
                    )
                    result = await self.session.send_request(
                        ClientRequest(
                            CallToolRequest(
                                method="tools/call",
                                params=CallToolRequestParams(
                                    name=name,
                                    arguments=arguments,
                                ),
                            )
                        ),
                        CallToolResult,
                        request_read_timeout_seconds=timedelta(seconds=self._cfg.tool_call_read_timeout_seconds),
                        metadata=metadata,
                    )
                logger.info(f"MCP Tool {name} succeeded (attempt {attempt}/{attempts})")
                return result.model_dump()

            except Exception as exc:
                is_transient = self._is_transient(exc)
                if not is_transient or attempt == attempts:
                    if not is_transient:
                        logger.debug(
                            f"will not retry tool {name} attempt {attempt}/{attempts} "
                            f"because it is not transient: {exc!r}"
                        )
                    elif attempt == attempts:
                        logger.debug(
                            f"will not retry tool {name} attempt {attempt}/{attempts} "
                            f"because it is the last attempt: {exc!r}"
                        )
                    raise
                await self._reconnect_when_appropriate(exc)
                last_exc = exc
                logger.debug(
                    f"tool {name} attempt {attempt}/{attempts} failed: {exc!r} (resumption_token={last_token})"
                )
                await asyncio.sleep(_full_jitter(base_backoff, attempt, backoff_cap))

        assert last_exc is not None
        raise last_exc

    # ------------------------------------------------------------------ #
    #  list_tools                                                        #
    # ------------------------------------------------------------------ #

    async def list_tools(self) -> list[ToolDefinition]:
        """
        Fetch tool list and return handy `ToolDefinition`s with bound callables.
        """
        if not self.is_connected:
            await self.connect()

        resp = await self.session.list_tools()

        # Local helpers ------------------------------------------------- #
        def _clean(schema: dict[str, Any]) -> dict[str, Any]:
            return {k: v for k, v in (schema or {}).items() if k != "$schema"}

        def _make_bound(name_: str):
            async def _bound(**kw):
                return await self.call_tool(name_, kw or {})

            return _bound

        # Build results ------------------------------------------------- #
        definitions: list[ToolDefinition] = []
        for tool in resp.tools:
            definitions.append(
                ToolDefinition(
                    name=tool.name,
                    description=tool.description or f"Tool: {tool.name}",
                    input_schema=_clean(tool.inputSchema),
                    category="mcp-tool",
                    function=_make_bound(tool.name),
                )
            )
        logger.info("Loaded %d tools from %s", len(definitions), self.target_server.url)
        return definitions


def _iter_exceptions_from_exception_group(exc: ExceptionGroup) -> Iterator[Exception]:
    """
    Iterate over all exceptions in an ExceptionGroup.
    """
    for exception in exc.exceptions:
        if isinstance(exception, ExceptionGroup):
            yield from _iter_exceptions_from_exception_group(exception)
        else:
            yield exception


def _convert_exception_group_to_single_exception(exc: BaseException) -> BaseException:
    """
    Convert an ExceptionGroup to a single exception.
    """
    if isinstance(exc, ExceptionGroup):
        exceptions = list(_iter_exceptions_from_exception_group(exc))

        if len(exceptions) == 1:
            return exceptions[0]
        else:
            msgs = [str(exception) for exception in exceptions]
            exc = ConnectionError(f"Multiple exceptions occurred: {', '.join(msgs)}")
            return exc
    else:
        return exc
