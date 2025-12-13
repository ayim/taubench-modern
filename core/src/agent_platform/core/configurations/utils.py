from dataclasses import is_dataclass
from types import NoneType, UnionType
from typing import Any, Union


def _get_union_args(t: type | Any) -> tuple[type, ...]:
    """Get the arguments of a Union type."""
    if isinstance(t, UnionType):
        return t.__args__
    # Typechecking note: The Union type instantiates a _UnionGenericAlias type,
    # which adds the __args__ attribute to the type, so this should always work.
    return getattr(t, "__args__", ())


def is_union_of_dataclasses_type(t: type | Any) -> bool:
    """Check if a type is a Union type."""
    is_union = getattr(t, "__origin__", None) is Union or isinstance(t, UnionType) or isinstance(t, type(Union))
    if not is_union:
        return False

    args = _get_union_args(t)
    # Check if the Union type is of dataclasses and None
    return all(is_dataclass(arg) for arg in args if arg is not NoneType and arg is not None)


def is_optional_type(t: type | Any) -> bool:
    """Check if a type is an Optional type."""
    return (
        getattr(t, "__origin__", None) is Union
        or isinstance(t, UnionType)
        or (isinstance(t, type(Union)) and NoneType in _get_union_args(t))
    )
