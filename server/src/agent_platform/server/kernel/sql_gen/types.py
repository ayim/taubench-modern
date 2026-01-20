"""Type definitions for SQL generation query verification."""

from typing import Literal

from pydantic import BaseModel


class Column(BaseModel):
    """A column in a query result."""

    name: str
    type: str


class Result(BaseModel):
    """The shape of a query result extracted from a dataframe."""

    columns: list[Column]
    row_count: int


class Shape(BaseModel):
    """The expected shape predicted by the LLM."""

    expected_columns: list[Column]
    row_cardinality: Literal["one_row", "many_rows"]


class Feedback(BaseModel):
    """Feedback from comparing actual vs expected shape."""

    feedback: list[str]
