"""Metadata-specific delta functions."""

from agent_server_types_v2.streaming.generic.compute_delta import compute_generic_delta
from agent_server_types_v2.streaming.generic.delta import GenericDelta

__all__ = [
    "GenericDelta",
    "compute_generic_delta",
]
