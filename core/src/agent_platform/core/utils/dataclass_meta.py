import dataclasses
from typing import Any


class _FilterKwargsMeta(type):
    """Metaclass that filters out unexpected keyword arguments.

    When instances of dataclasses using this metaclass are created, either directly or through
    helper constructors like ``model_validate`` that forward keyword arguments, any unexpected
    keyword arguments will be ignored instead of raising ``TypeError``.
    """

    def __call__(cls, *args: Any, **kwargs: Any):  # type: ignore[override]
        if kwargs:
            valid = {field.name for field in dataclasses.fields(cls)}  # pyright: ignore[reportArgumentType]
            kwargs = {key: value for key, value in kwargs.items() if key in valid}
        return super().__call__(*args, **kwargs)


class TolerantDataclass(metaclass=_FilterKwargsMeta):
    """Base class for dataclasses that ignore unexpected keyword arguments."""


__all__ = ["TolerantDataclass"]
