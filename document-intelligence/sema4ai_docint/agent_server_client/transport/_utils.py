"""Internal utility functions for working with transport protocols."""

import asyncio
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Any

from .base import TransportBase
from .direct import DirectTransport


@asynccontextmanager
async def get_file_async(
    transport: TransportBase | DirectTransport,
    name: str,
    thread_id: str | None = None,
) -> AsyncIterator[Path]:
    """Get a file as an async context manager, handling both sync and async transports.

    This helper allows async code to use the file context manager with both
    sync (TransportBase) and async (DirectTransport) transports. For sync
    transports, the context manager operations are run in a thread pool.

    Args:
        transport: The transport instance (TransportBase or DirectTransport)
        name: The file reference/name to retrieve
        thread_id: Optional thread ID override

    Yields:
        Path: Path to the file on the local filesystem
    """
    if isinstance(transport, TransportBase):
        # Sync transport - wrap in thread for enter/exit
        ctx = transport.get_file(name, thread_id)
        path = await asyncio.to_thread(ctx.__enter__)
        try:
            yield path
        finally:
            await asyncio.to_thread(ctx.__exit__, None, None, None)
    else:
        # DirectTransport (async) - use directly
        async with transport.get_file(name, thread_id) as path:
            yield path


@contextmanager
def get_file_sync(
    transport: TransportBase | DirectTransport,
    name: str,
    thread_id: str | None = None,
) -> Iterator[Path]:
    """Get a file as a sync context manager, handling both sync and async transports.

    This helper allows sync code to use the file context manager with both
    sync (TransportBase) and async (DirectTransport) transports. For async
    transports, the async operations are run synchronously (blocking).

    Args:
        transport: The transport instance (TransportBase or DirectTransport)
        name: The file reference/name to retrieve
        thread_id: Optional thread ID override

    Yields:
        Path: Path to the file on the local filesystem

    Raises:
        RuntimeError: If called from an async context
    """
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        pass
    else:
        raise RuntimeError(
            "get_file_sync() called from an async context. "
            "Use: async with get_file_async(...) instead."
        )

    # Sync transport - use directly
    if isinstance(transport, TransportBase):
        with transport.get_file(name, thread_id) as path:
            yield path
    else:
        # Async transport - run synchronously (blocking)
        # We manually manage the async context manager lifecycle
        async def _aenter():
            ctx = transport.get_file(name, thread_id)
            path = await ctx.__aenter__()
            return path, ctx

        path, ctx = asyncio.run(_aenter())
        try:
            yield path
        finally:
            # Ensure cleanup happens even if an exception is raised
            asyncio.run(ctx.__aexit__(None, None, None))


async def call_transport_method_async(
    transport: TransportBase | DirectTransport,
    method_name: str,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Call a transport method from an async context, handling both sync and async transports.

    This helper function allows async code to work with both sync and async transports.
    When using DirectTransport (async), it awaits directly. When using TransportBase (sync),
    it runs the sync method in a thread pool to avoid blocking the event loop.

    Args:
        transport: The transport instance (TransportBase or DirectTransport)
        method_name: Name of the transport method to call
        *args: Positional arguments to pass to the method
        **kwargs: Keyword arguments to pass to the method

    Returns:
        The result of the transport method call
    """
    method = getattr(transport, method_name)

    # Check TransportBase first (concrete class) to avoid protocol matching overlap
    # since TransportBase now implements the same method names as DirectTransport
    if isinstance(transport, TransportBase):
        # TransportBase methods are sync - run in thread pool to avoid blocking
        return await asyncio.to_thread(method, *args, **kwargs)
    else:
        # DirectTransport methods are async - await directly
        return await method(*args, **kwargs)


def call_transport_method(
    transport: TransportBase | DirectTransport,
    method_name: str,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Call a transport method from a sync context, handling both sync and async transports.

    This helper function allows sync code to work with both sync and async transports.
    It runs call_transport_method_async in a new event loop. For TransportBase (sync),
    it runs in a thread pool. For DirectTransport (async), it creates an event loop.

    Args:
        transport: The transport instance (TransportBase or DirectTransport)
        method_name: Name of the transport method to call
        *args: Positional arguments to pass to the method
        **kwargs: Keyword arguments to pass to the method

    Returns:
        The result of the transport method call

    Raises:
        RuntimeError: If called from an async context (use call_transport_method_async instead)
    """
    # If we're already in an event-loop thread, don't block it.
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # Normal sync context: use asyncio.run() which properly manages its own event loop
        return asyncio.run(call_transport_method_async(transport, method_name, *args, **kwargs))

    raise RuntimeError(
        f"call_transport_method('{method_name}') called from an async context. "
        f"Use: await call_transport_method_async(transport, '{method_name}', ...) instead."
    )
