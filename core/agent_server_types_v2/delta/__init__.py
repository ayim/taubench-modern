"""This module contains the logic for computing and combining delta objects
for generic objects (they must be JSON serializable).

The module implements JSON Patch (RFC 6902) operations with extensions.
All operations use JSON Pointer (RFC 6901) for addressing.

Standard JSON Patch operations (RFC 6902):
- `add`: Add a value at the target location
- `remove`: Remove the value at the target location
- `replace`: Replace the value at the target location
- `move`: Move a value from one location to another
- `copy`: Copy a value from one location to another
- `test`: Test that a value at the target location equals the specified value

Extended operations:
- `concat_string`: Concatenate a string to the value at the path
- `inc`: Increment the value at the path by the specified amount

The `compute_generic_delta` function computes the delta between two
generic objects, using specialized operations where possible (e.g.,
string concatenation, increments) and falling back to standard JSON
Patch operations otherwise.

The `combine_generic_deltas` function combines a list of delta objects
back into a single object, applying each operation in sequence according
to RFC 6902 rules.

Note that `None` is a valid value for operations that accept values
(add, replace, test, concat_string, inc). Operations that don't accept
values (remove, move, copy) must use the special sentinel NO_VALUE.
"""

from agent_server_types_v2.delta.base import (
    NO_VALUE,
    DeltaOpType,
    GenericDelta,
)
from agent_server_types_v2.delta.combine_delta import combine_generic_deltas
from agent_server_types_v2.delta.compute_delta import compute_generic_deltas

__all__ = [
    "NO_VALUE",
    "DeltaOpType",
    "GenericDelta",
    "combine_generic_deltas",
    "compute_generic_deltas",
]
