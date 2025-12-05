"""Mapping models for document transformation."""

from typing import Literal

from pydantic import BaseModel, Field

Mode = Literal["flatten"]
Transform = Literal["int", "float", "str", "bool"]


class MappingRow(BaseModel):
    """
    An object that describes the mapping of one field in a Mapping.

    Attributes
    ----------
    source : str
        Dotted JSON path in the source document.
        Use `[*]` to denote "all elements" of an array, e.g. `order.items[*]`.
    target : str
        Dotted path in the output object where the value(s) should be written.
    mode : Optional[str], default None
        * flatten - emit one new output object per element and merge `extras`.
    transform : Optional[str], default None
        Optional cast or conversion (e.g. "int", "float", "timestamp").
    extras : dict[str, str], default {}
        Only used when mode == "flatten".
        Maps new field-names → relative paths of attributes to lift.
    """

    source: str
    target: str
    mode: Mode | None = None
    transform: Transform | None = None
    extras: dict[str, str] = Field(default_factory=dict)


class Mapping(BaseModel):
    """
    An object that describes the mapping from one JSON object to another.

    Attributes
    ----------
    rules : list[MappingRow]
        List of mapping rules to apply for the transformation.
    """

    rules: list[MappingRow]
