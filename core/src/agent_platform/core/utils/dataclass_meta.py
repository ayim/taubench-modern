from typing import Any


class _FilterKwargsMeta(type):
    """Metaclass that filters out unexpected keyword arguments.

    When instances of dataclasses using this metaclass are created, either directly or through
    helper constructors like ``model_validate`` that forward keyword arguments, any unexpected
    keyword arguments will be ignored instead of raising ``TypeError``.
    """

    def __call__(cls, *args: Any, **kwargs: Any):  # type: ignore[override]
        if kwargs:
            # Python dataclasses have a __dataclass_fields__ dict: field to attribute
            # metadata. We expect this to fail if someone uses this metadata class _not_
            # on a Python dataclass.
            actual_fields = getattr(cls, "__dataclass_fields__")  # noqa: B009
            kwargs = {key: value for key, value in kwargs.items() if key in actual_fields}
        return super().__call__(*args, **kwargs)


class TolerantDataclass(metaclass=_FilterKwargsMeta):
    """Base class for dataclasses that ignore unexpected keyword arguments."""


__all__ = ["TolerantDataclass"]
