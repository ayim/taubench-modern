from dataclasses import fields, is_dataclass
from typing import Any


def user_scoped(**kwargs: Any) -> dict[str, Any]:
    """
    Marks a dataclass field as user-scoped.

    Arguments:
        **kwargs: Additional metadata (e.g., a description) to attach.

    Returns:
        A dict with a 'scope' set to 'user', merged with additional data.
    """
    metadata = {"scope": "user"}
    metadata.update(kwargs)
    return metadata

def thread_scoped(**kwargs: Any) -> dict[str, Any]:
    """
    Marks a dataclass field as thread-scoped.

    Arguments:
        **kwargs: Additional metadata (e.g., a description) to attach.

    Returns:
        A dict with a 'scope' set to 'thread', merged with additional data.
    """
    metadata = {"scope": "thread"}
    metadata.update(kwargs)
    return metadata

def agent_scoped(**kwargs: Any) -> dict[str, Any]:
    """
    Marks a dataclass field as agent-scoped.

    Arguments:
        **kwargs: Additional metadata (e.g., a description) to attach.

    Returns:
        A dict with a 'scope' set to 'agent', merged with additional data.
    """
    metadata = {"scope": "agent"}
    metadata.update(kwargs)
    return metadata

def get_fields_by_scope(state_obj: Any, scope: str) -> dict[str, Any]:
    """
    Examines the state object's dataclass fields and returns a dictionary
    of field names mapped to their values for the given scope.

    This can be useful in a @step decorator for restoring or handling a subset
    of the state based on its metadata.

    Arguments:
        state_obj: An instance of a dataclass that has metadata attached to its fields.
        scope: A string indicating the desired scope ('user', 'thread', or 'agent').

    Returns:
        A dict mapping field names to their values if the field's metadata scope
        matches.
    """
    assert scope in ["user", "thread", "agent"], (
        f"Invalid scope: {scope} (must be one of 'user', 'thread', or 'agent')"
    )
    assert is_dataclass(state_obj), "State object must be a dataclass"

    return {
        field_obj.name: getattr(state_obj, field_obj.name)
        for field_obj in fields(state_obj)
        if field_obj.metadata.get('scope') == scope
    }
