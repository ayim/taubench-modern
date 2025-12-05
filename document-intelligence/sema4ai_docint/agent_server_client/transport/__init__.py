"""Transport implementations for AgentServerClient."""

import importlib.util

from .base import (
    ResponseMessage,
    TransportBase,
    TransportResponseWrapper,
)
from .http import HTTPTransport

__all__ = [
    "HTTPTransport",
    "ResponseMessage",
    "TransportBase",
    "TransportResponseWrapper",
]

# Optional import for MemoryTransport (requires fastapi extra)
if importlib.util.find_spec("fastapi") is not None:
    from .memory import MemoryTransport  # noqa: F401

    __all__.append("MemoryTransport")
