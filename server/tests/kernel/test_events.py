import asyncio
from collections.abc import Callable
from typing import Final

import pytest

from agent_platform.server.kernel.events import AgentServerEventsInterface

# ────────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────────
_EVENT_A: Final[int] = 1
_EVENT_B: Final[int] = 2


def _is_event(value: int) -> Callable[[int], bool]:
    """Return a predicate that matches a specific integer event."""
    return lambda e: e == value


# ────────────────────────────────────────────────────────────────────────────────
# Tests
# ────────────────────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_stream_yields_events_in_order() -> None:
    """`stream()` yields dispatched events in the same order they arrived."""
    bus = AgentServerEventsInterface[int]()

    async def producer() -> None:
        await bus.dispatch(_EVENT_A)
        await bus.dispatch(_EVENT_B)
        await bus.stop()

    async def consumer(collected: list[int]) -> None:
        async for item in bus.stream():
            collected.append(item)

    collected: list[int] = []
    # Run producer & consumer concurrently and wait for both to finish.
    await asyncio.gather(producer(), consumer(collected))

    assert collected == [_EVENT_A, _EVENT_B]


@pytest.mark.asyncio
async def test_wait_for_event_returns_matching_item() -> None:
    bus = AgentServerEventsInterface[int]()

    waiter_task = asyncio.create_task(bus.wait_for_event(_is_event(_EVENT_B)))
    await asyncio.sleep(0)  # give waiter a chance to register

    await bus.dispatch(_EVENT_A)
    await bus.dispatch(_EVENT_B)

    result = await asyncio.wait_for(waiter_task, timeout=1.0)
    assert result == _EVENT_B


@pytest.mark.asyncio
async def test_multiple_waiters_only_matching_waiter_resolves() -> None:
    bus = AgentServerEventsInterface[int]()

    waiter_a = asyncio.create_task(bus.wait_for_event(_is_event(_EVENT_A)))
    waiter_b = asyncio.create_task(bus.wait_for_event(_is_event(_EVENT_B)))
    await asyncio.sleep(0)  # both waiters installed

    await bus.dispatch(_EVENT_B)  # Only waiter_b should resolve.

    assert await asyncio.wait_for(waiter_b, 1.0) == _EVENT_B
    assert not waiter_a.done()

    await bus.dispatch(_EVENT_A)
    assert await asyncio.wait_for(waiter_a, 1.0) == _EVENT_A


@pytest.mark.asyncio
async def test_dispatch_after_stop_raises() -> None:
    """Calling `dispatch` after `stop` raises `RuntimeError`."""
    bus = AgentServerEventsInterface[int]()
    await bus.stop()

    with pytest.raises(RuntimeError):
        await bus.dispatch(_EVENT_A)


@pytest.mark.asyncio
async def test_stop_unblocks_stream_and_pulls_waiters_off_the_bus() -> None:
    """
    `stop()` must:
      • make any active `stream()` terminate cleanly,
      • and ensure pending `wait_for_event()` callers finish
        (either via cancellation or the explicit RuntimeError guard).
    """
    bus = AgentServerEventsInterface[int]()

    # Long-lived stream consumer ─ will exit only when the sentinel is seen.
    stream_finished = asyncio.Event()

    async def consume() -> None:
        async for _ in bus.stream():
            pass
        stream_finished.set()

    stream_task = asyncio.create_task(consume())

    # Waiter that will never match.
    waiter_task = asyncio.create_task(bus.wait_for_event(_is_event(999)))

    # Stop the bus.
    await bus.stop()

    # -- 1. the stream should have finished ------------------------------
    await asyncio.wait_for(stream_finished.wait(), 0.1)
    assert stream_task.done()
    assert stream_task.exception() is None

    # -- 2. the waiter should be finished one way or another -------------
    assert waiter_task.done()

    if waiter_task.cancelled():
        # Cancelled path is fine.
        return

    # Otherwise it must have raised the explicit RuntimeError guard.
    exc = waiter_task.exception()
    assert isinstance(exc, RuntimeError)
    assert str(exc) == "Event bus has been stopped"


@pytest.mark.asyncio
async def test_wait_for_event_errors_if_bus_already_stopped() -> None:
    """Calling `wait_for_event` after `stop()` should fail immediately."""
    bus = AgentServerEventsInterface[int]()
    await bus.stop()

    with pytest.raises(RuntimeError):
        await bus.wait_for_event(_is_event(_EVENT_A))


@pytest.mark.asyncio
async def test_many_waiters_same_predicate_resolve():
    bus = AgentServerEventsInterface[int]()
    waiters = [asyncio.create_task(bus.wait_for_event(_is_event(_EVENT_A))) for _ in range(3)]
    await asyncio.sleep(0)
    await bus.dispatch(_EVENT_A)
    assert [await w for w in waiters] == [_EVENT_A, _EVENT_A, _EVENT_A]


@pytest.mark.asyncio
async def test_stop_is_idempotent():
    bus = AgentServerEventsInterface[int]()
    await bus.stop()
    # second call should neither raise nor hang
    await bus.stop()


@pytest.mark.asyncio
async def test_stream_started_after_stop_finishes_immediately():
    bus = AgentServerEventsInterface[int]()
    await bus.stop()
    gen = bus.stream()
    with pytest.raises(StopAsyncIteration):
        await gen.__anext__()
