import json
from dataclasses import dataclass, fields


@dataclass
class StateBase:
    """
    Base state dataclass that validates that all scoped fields are JSON serializable.

    Scoped fields are those with a metadata 'scope' ('user', 'thread', or 'agent').
    This ensures that areas of state intended for JSON persistence will not cause errors
    when being backed by a JSON database.
    """
    def __post_init__(self):
        # Iterate over all fields in the dataclass
        for field_obj in fields(self):
            # Check if the field has a 'scope' set in its metadata
            scope = field_obj.metadata.get("scope", None)
            if scope is None or scope not in ["user", "thread", "agent"]:
                continue

            value = getattr(self, field_obj.name)
            try:
                # This will raise an exception if the value is not JSON serializable
                json.dumps(value)
            except (TypeError, ValueError) as e:
                raise ValueError(
                    f"The field '{field_obj.name}' with scope"
                    f" '{scope}' is not JSON serializable: {e}",
                ) from e
