import asyncio
import json
import types
from typing import Any

import pytest

from agent_platform.core.responses.content.tool_use import ResponseToolUseContent
from agent_platform.core.tools import ToolDefinition
from agent_platform.server.configuration_manager import ConfigurationService
from agent_platform.server.kernel.kernel_mixin import UsesKernelMixin
from agent_platform.server.kernel.tools import (
    AgentServerToolsInterface,
)
from agent_platform.server.kernel.tools_caching import (
    ToolCacheConfig,
    ToolDefinitionCache,
)

# ---------------------------------------------------------------------------
# Very small doubles / stubs so we don't have to pull a real kernel into tests
# ---------------------------------------------------------------------------


class _DummySpan:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    # no-ops: we just need the attributes to be present
    def set_attribute(self, *_, **__):
        pass

    def add_event(self, *_, **__):
        pass

    def set_status(self, *_, **__):
        pass


class _DummyCtx:
    def start_span(self, *_, **__):
        return _DummySpan()


class _DummyKernel:
    """Bare-minimum façade that the interface touches."""

    def __init__(self) -> None:
        self.ctx = _DummyCtx()
        self.agent = types.SimpleNamespace(
            agent_id="agent-1", action_packages=[], mcp_servers=[]
        )
        self.user = types.SimpleNamespace(user_id="user-1")
        self.thread = types.SimpleNamespace(thread_id="thread-1")


class _MessageRecorder:
    """Captures calls that the interface makes while tools are running."""

    def __init__(self) -> None:
        self.running_calls: list[str] = []
        self.done_results: list[Any] = []

    # synchronous in the production class
    def update_tool_running(self, tool_call_id: str) -> None:
        self.running_calls.append(tool_call_id)

    async def stream_delta(self) -> None:
        # nothing to stream --- we just satisfy the awaited call
        return None

    def update_tool_result(self, result) -> None:
        self.done_results.append(result)


class _StubActionPackage:
    """Just enough API surface so _fetch_action_tools()
    can call .to_tool_definitions()."""

    def __init__(self, url: str, tool_defs: list[ToolDefinition] | None = None):
        self.name = "pkg"
        self.version = "1.0"
        self.url = url
        self._tool_defs = tool_defs or [_dummy_tool(name=f"T{url[-1]}")]

    async def to_tool_definitions(self, _headers=None):
        async def _get_tool_def_async(td):
            await asyncio.sleep(0.01)
            return td

        for td in self._tool_defs:
            yield await _get_tool_def_async(td)


# ---------------------------------------------------------------------------
# tiny helper to build dummy ResponseToolUseContent instances on the fly.
# The real class has *lots* of attributes; we only need the two that the
# interface actually reads (`tool_call_id`, `tool_input_raw`).
# ---------------------------------------------------------------------------


def _stub_tool_use(
    tool_call_id: str,
    tool_input_raw: str = "",
    tool_name: str = "Echo",
) -> ResponseToolUseContent:
    return ResponseToolUseContent(
        tool_call_id=tool_call_id,
        tool_input_raw=tool_input_raw,
        tool_name=tool_name,
    )


def _dummy_tool(name: str = "T") -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description="",
        input_schema={},
        function=lambda **_: None,
    )


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def kernel() -> _DummyKernel:
    return _DummyKernel()


@pytest.fixture
def iface(kernel) -> AgentServerToolsInterface:
    """Concrete instance of the interface with our dummy kernel injected."""

    class _Concrete(AgentServerToolsInterface, UsesKernelMixin):  # type: ignore[override]
        def __init__(self, _kernel):
            self._internal_kernel = _kernel

    return _Concrete(kernel)


@pytest.fixture(autouse=True)
def _reset_tool_cache():
    """Flush ALL in-memory caches before and after each caching test."""
    ToolDefinitionCache().clear_all()
    yield
    ToolDefinitionCache().clear_all()


@pytest.fixture(autouse=True)
def _reset_config_service():
    saved = ConfigurationService.get_instance(reinitialize=True)
    ConfigurationService.set_for_testing(saved)
    yield
    ConfigurationService.reset()


# ---------------------------------------------------------------------------
# 1.  D E - D U P L I C A T I O N
# ---------------------------------------------------------------------------


def test_deduplicate_tool_names() -> None:
    t1 = ToolDefinition(
        name="Echo", description="d1", input_schema={}, function=lambda **_: None
    )
    t2 = ToolDefinition(
        name="Echo", description="d2", input_schema={}, function=lambda **_: None
    )
    t3 = ToolDefinition(
        name="Add", description="d3", input_schema={}, function=lambda **_: None
    )

    renamed, issues = AgentServerToolsInterface._deduplicate_tool_names([t1, t2, t3])
    names = [t.name for t in renamed]

    assert names == ["Echo", "Echo_2", "Add"]
    assert any("duplicated" in msg.lower() for msg in issues)


# ---------------------------------------------------------------------------
# 2.  S A F E   E X E C U T I O N   W R A P P E R
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_safe_execute_tool_success(iface: AgentServerToolsInterface) -> None:
    async def echo(msg: str, extra_headers=None):
        return {"echo": msg, "headers": extra_headers or {}}

    tool_def = ToolDefinition(
        name="EchoTool",
        description="Echos the incoming message.",
        input_schema={"type": "object", "properties": {"msg": {"type": "string"}}},
        function=echo,
    )

    tool_use = _stub_tool_use("call-1", json.dumps({"msg": "hello"}))

    result = await iface._safe_execute_tool(tool_def, tool_use)

    assert result.error is None
    assert result.output_raw is not None
    assert result.output_raw["echo"] == "hello"
    # extra headers are injected by the caller of _safe_execute_tool
    assert "headers" in result.output_raw


@pytest.mark.asyncio
async def test_safe_execute_tool_runtime_error(
    iface: AgentServerToolsInterface,
) -> None:
    async def boom(*_, **__) -> None:
        raise RuntimeError("💥 kaboom")

    tool_def = ToolDefinition(
        name="Boom", description="", input_schema={}, function=boom
    )
    tool_use = _stub_tool_use("call-boom", "{}")

    result = await iface._safe_execute_tool(tool_def, tool_use)

    assert result.output_raw is None
    assert result.error
    assert "kaboom" in result.error


# ---------------------------------------------------------------------------
# 3.  B A T C H   /   A S Y N C   T O O L   E X E C U T I O N
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_pending_tool_calls_runs_everything(
    iface: AgentServerToolsInterface,
) -> None:
    async def plus(a: int, b: int, extra_headers=None):
        return a + b

    async def upper(text: str, extra_headers=None):
        return text.upper()

    add_def = ToolDefinition(name="Add", description="", input_schema={}, function=plus)
    up_def = ToolDefinition(
        name="Upper", description="", input_schema={}, function=upper
    )

    pending: list[tuple[ToolDefinition, ResponseToolUseContent]] = [
        (add_def, _stub_tool_use("tc-add", json.dumps({"a": 2, "b": 3}))),
        (up_def, _stub_tool_use("tc-upper", json.dumps({"text": "ok"}))),
    ]

    recorder = _MessageRecorder()
    results = [
        r
        async for r in iface.execute_pending_tool_calls(
            pending.copy(),
            recorder,  # type: ignore[arg-type] (just for testing)
        )
    ]

    # every tool should finish
    assert {r.definition.name for r in results} == {"Add", "Upper"}

    add_res = next(r for r in results if r.definition.name == "Add")
    up_res = next(r for r in results if r.definition.name == "Upper")

    assert add_res.output_raw == 5
    assert up_res.output_raw == "OK"

    # progress callbacks fired exactly once per tool
    assert set(recorder.running_calls) == {"tc-add", "tc-upper"}
    assert {r.tool_call_id for r in recorder.done_results} == {"tc-add", "tc-upper"}


# ---------------------------------------------------------------------------
# scenario A: plain hit after a successful fetch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_hit_after_first_fetch(
    iface: AgentServerToolsInterface,
    monkeypatch,
):
    fetch_counter = {"n": 0}

    async def fake_fetch(pkgs, additional_headers=None):
        fetch_counter["n"] += 1
        collected_tools = []
        for pkg in pkgs:
            async for tool_def in pkg.to_tool_definitions(additional_headers):
                collected_tools.append(tool_def)

        # one tool per package
        return (collected_tools, [])

    monkeypatch.setattr(iface, "_fetch_action_tools", fake_fetch)

    pkg = _StubActionPackage("https://pkg1")
    tools1, _ = await iface.from_action_packages([pkg])  # type: ignore[arg-type]
    tools2, _ = await iface.from_action_packages([pkg])  # type: ignore[arg-type]

    # fetch happened exactly once, second call read from cache
    assert fetch_counter["n"] == 1
    assert [t.name for t in tools1] == [t.name for t in tools2]


# ---------------------------------------------------------------------------
# scenario B: TTL expiry triggers a refresh (miss --> hit)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_refresh_after_ttl_expiry(
    iface: AgentServerToolsInterface,
    monkeypatch,
):
    # shorten TTL for the test and restore afterwards
    manager = ConfigurationService.get_instance()
    manager.update_configuration(
        ToolCacheConfig,
        ToolCacheConfig(
            ttl_seconds=0,
        ),
    )

    ToolDefinitionCache.reinitialize()
    iface._cache = ToolDefinitionCache()

    fetch_counter = {"n": 0}

    async def fake_fetch(pkgs, additional_headers=None):
        fetch_counter["n"] += 1
        suffix = f"{fetch_counter['n']}"
        return (
            [
                ToolDefinition(
                    name=f"T{suffix}",
                    description="",
                    input_schema={},
                    function=lambda **_: None,
                )
            ],
            [],
        )

    monkeypatch.setattr(iface, "_fetch_action_tools", fake_fetch)

    pkg = _StubActionPackage("https://pkg2")
    tools1, _ = await iface.from_action_packages([pkg])  # type: ignore[arg-type]

    tools2, _ = await iface.from_action_packages([pkg])  # type: ignore[arg-type]

    # second call forced a re-fetch
    assert fetch_counter["n"] == 2
    assert tools1[0].name != tools2[0].name  # proved we received a fresh list


# ---------------------------------------------------------------------------
# scenario C: negative-TTL (failed fetch) is cached but refreshed
#             once the *negative* TTL has elapsed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_negative_cache_ttl(iface: AgentServerToolsInterface, monkeypatch):
    manager = ConfigurationService.get_instance()
    manager.update_configuration(
        ToolCacheConfig,
        ToolCacheConfig(
            negative_ttl_seconds=0,
        ),
    )

    ToolDefinitionCache.reinitialize()
    iface._cache = ToolDefinitionCache()

    fetch_counter = {"n": 0}

    async def fake_fetch_failure(pkgs, additional_headers=None):
        fetch_counter["n"] += 1
        return ([], ["boom"])

    monkeypatch.setattr(iface, "_fetch_action_tools", fake_fetch_failure)

    pkg = _StubActionPackage("https://pkg3")

    # 1) initial failure --> cached (negative)
    _, issues1 = await iface.from_action_packages([pkg])  # type: ignore[arg-type]
    # 2) cache expired immediately, triggers second fetch
    _, issues2 = await iface.from_action_packages([pkg])  # type: ignore[arg-type]

    assert fetch_counter["n"] == 2
    assert issues1
    assert issues2  # both calls report the failure


# ---------------------------------------------------------------------------
# scenario D: test that the cache waits for the refresh to complete
#             when a refresh is already running in another coroutine
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_waits_for_refresh(
    iface: AgentServerToolsInterface,
    monkeypatch,
):
    fetch_counter = {"n": 0}

    async def slow_fetch(pkgs, additional_headers=None):
        fetch_counter["n"] += 1
        await asyncio.sleep(0.2)  # pretend network latency
        return ([_dummy_tool("Slow")], [])

    monkeypatch.setattr(iface, "_fetch_action_tools", slow_fetch)

    pkg = _StubActionPackage("https://pkg4")

    async def first_call():
        # grabs the lock and does the real fetch
        return await iface.from_action_packages([pkg])  # type: ignore[arg-type]

    async def second_call():
        # will block on the same lock and get the fresh value
        return await iface.from_action_packages([pkg])  # type: ignore[arg-type]

    task1 = asyncio.create_task(first_call())
    await asyncio.sleep(0.05)  # let task1 acquire the lock

    tools2, _ = await second_call()  # no tiny timeout: we expect to wait
    tools1, _ = await task1  # fetch completes

    assert fetch_counter["n"] == 1  # only one real fetch
    assert [t.name for t in tools1] == ["Slow"]
    assert [t.name for t in tools2] == ["Slow"]


# ---------------------------------------------------------------------------
# scenario E: cache disabled via environment variable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cache_disabled_via_env_var(
    iface: AgentServerToolsInterface,
    monkeypatch,
):
    # Set the environment variable to disable the cache
    monkeypatch.setenv("SEMA4AI_AGENT_SERVER_TOOL_CACHE_ENABLED", "false")

    # Reinitialize ConfigurationService to pick up the env var
    # and update the ToolCacheConfig
    ConfigurationService.get_instance(reinitialize=True)
    # Verify that the config is indeed disabled
    assert not ToolCacheConfig.enabled

    ToolDefinitionCache.reinitialize()
    iface._cache = ToolDefinitionCache()

    fetch_counter = {"n": 0}

    async def fake_fetch(pkgs, additional_headers=None):
        fetch_counter["n"] += 1
        collected_tools = []
        for pkg in pkgs:
            async for tool_def in pkg.to_tool_definitions(additional_headers):
                collected_tools.append(tool_def)
        return (collected_tools, [])

    monkeypatch.setattr(iface, "_fetch_action_tools", fake_fetch)

    pkg = _StubActionPackage("https://pkg-cache-disabled")
    tools1, _ = await iface.from_action_packages([pkg])  # type: ignore[arg-type]
    tools2, _ = await iface.from_action_packages([pkg])  # type: ignore[arg-type]

    # Fetch should happen twice because caching is disabled
    assert fetch_counter["n"] == 2
    assert [t.name for t in tools1] == [t.name for t in tools2]
    assert tools1[0].name == "Td"
    assert tools2[0].name == "Td"
