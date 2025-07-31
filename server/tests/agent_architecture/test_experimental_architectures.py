import types

import pytest

from agent_platform.server.agent_architectures.arch_manager import (
    AgentArchManager,
)
from agent_platform.server.agent_architectures.in_process_runner import (
    InProcessAgentRunner,
)


class _DummyEventStream:
    """Minimal async iterator that immediately terminates."""

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


class _DummyEvents:
    async def dispatch(self, _event):
        return None

    def stream(self):
        return _DummyEventStream()


class _DummyKernel:
    """Very small stand-in for `agent_platform.core.kernel.Kernel`."""

    def __init__(self):
        self.outgoing_events = _DummyEvents()
        self.incoming_events = _DummyEvents()
        dummy_run = types.SimpleNamespace(
            run_id="run-id",
            thread_id="thread-id",
            agent_id="agent-id",
        )
        self.run = dummy_run


EXPERIMENTAL_PACKAGES = [
    "agent_platform.architectures.experimental_1",
    "agent_platform.architectures.experimental_2",
    "agent_platform.architectures.experimental_3",
]


@pytest.mark.unit
@pytest.mark.asyncio
@pytest.mark.parametrize("package_name", EXPERIMENTAL_PACKAGES)
async def test_experimental_runner_invokes_real_entrypoint(caplog, tmp_path, package_name):
    """Ensure that, for each experimental architecture, the in-process runner
    loads and invokes the real entrypoint function from the correct module.

    This test proves we actually reach the real architecture code, not just
    that some function gets called.
    """
    # Arrange: create a runner through the manager so we mimic real behaviour
    manager = AgentArchManager(wheels_path=str(tmp_path), websocket_addr="ws://test")
    version = "1.0.0"  # Version used in `AgentArchManager.in_process_allowlist`
    thread_id = "test-thread"

    runner = await manager.get_runner(package_name, version, thread_id)
    assert isinstance(runner, InProcessAgentRunner)

    # Start the runner to resolve the real entrypoint
    await runner.start()

    # Verify we loaded the real entrypoint, not a fake
    assert runner.entry_func is not None
    assert callable(runner.entry_func)

    # Verify that the runner's entry_func is actually from the expected module
    entry_func_module = runner.entry_func.__module__
    expected_module = f"agent_platform.architectures.experimental.exp_{package_name.split('_')[-1]}"
    assert entry_func_module == expected_module, (
        f"Expected entry function from module {expected_module}, got {entry_func_module}"
    )

    # Verify the function name matches what we expect
    expected_func_name = f"entrypoint_exp_{package_name.split('_')[-1]}"
    actual_func_name = (
        getattr(runner.entry_func, "__name__", None)
        or getattr(runner.entry_func, "__wrapped__", lambda: None).__name__
    )
    assert expected_func_name in str(actual_func_name), (
        f"Expected function name to contain '{expected_func_name}', got '{actual_func_name}'"
    )

    # Act: invoke the runner with a dummy kernel to prove it can be called
    dummy_kernel = _DummyKernel()

    # Clear any previous log messages
    caplog.clear()

    # Patch the specific entrypoint function to bypass decorator validation
    original_func = runner.entry_func

    # Extract the original function from the decorator wrapper
    if hasattr(original_func, "__wrapped__"):
        # Get the original function before decoration
        unwrapped_func = original_func.__wrapped__
    else:
        unwrapped_func = original_func

    # Create a simple wrapper that just calls the original with dummy state
    async def patched_entrypoint(kernel):
        # Call the original function with kernel and a dummy state
        from agent_platform.architectures.default.state import ArchState

        dummy_state = ArchState()
        return await unwrapped_func(kernel, dummy_state)  # type: ignore

    # Temporarily replace the entry function
    runner.entry_func = patched_entrypoint

    invocation_successful = False
    try:
        # This will call our patched entrypoint function
        await runner.invoke(dummy_kernel)  # type: ignore[arg-type]
        invocation_successful = True
    finally:
        # Restore the original function
        runner.entry_func = original_func

    # Assert: verify we successfully attempted to invoke the real architecture
    assert invocation_successful, f"Failed to invoke architecture {package_name}"


@pytest.mark.unit
def test_experimental_architectures_exposed():
    """`get_architectures` should include all experimental architectures so
    they are discoverable by the API layer."""

    arch_names = [arch.name for arch in InProcessAgentRunner.get_architectures()]

    missing = [pkg for pkg in EXPERIMENTAL_PACKAGES if pkg not in arch_names]
    assert not missing, f"Architectures missing from discovery: {missing}"
