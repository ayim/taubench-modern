"""Internal utility functions for working with transport protocols."""

import asyncio
from typing import Any

from .base import TransportBase
from .direct import DirectTransport


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
