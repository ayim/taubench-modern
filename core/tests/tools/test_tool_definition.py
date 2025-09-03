from dataclasses import dataclass, field
from enum import Enum
from typing import Annotated, Optional

import pytest

from agent_platform.core.tools.tool_definition import ToolDefinition

##################################################
# Example Enum to use in tests
##################################################


class ExampleEnum(Enum):
    RELEVANCE = "relevance"
    DATE = "date"
    POPULARITY = "popularity"
    ALPHABETICAL = "alphabetical"


##################################################
# Example Dataclasses to use in tests
##################################################


@dataclass
class PersonData:
    """Simple dataclass to test nested object schema."""

    name: Annotated[str, "Name of the person"]
    age: Optional[int] = None  # noqa: UP007 (we want to explicitly test)
    height: Annotated[float, "Height of the person in meters"] = 1.75


@dataclass
class ComplexDataWithListAndNestedPerson:
    """Complex dataclass to test list and nested object schema."""

    person: PersonData = field(metadata={"description": "A nested person object"})
    enum_value: Annotated[ExampleEnum, "An enum value"]
    values: list[str] = field(
        default_factory=list,
        metadata={"description": "A list of strings"},
    )


##################################################
# Tests for .from_callable
##################################################


def test_function_must_be_async():
    """Non-async functions should raise a ValueError."""

    def not_async(a: str):
        pass

    with pytest.raises(ValueError, match="must be async"):
        ToolDefinition.from_callable(
            not_async,  # type: ignore (testing invalid usage)
        )


async def dummy_no_params():
    """An async function with no parameters."""
    return "ok"


def test_async_function_no_params():
    """
    Even if a function has no parameters,
    we should successfully build a ToolDefinition.
    """
    tool = ToolDefinition.from_callable(dummy_no_params)
    assert tool.name == "dummy_no_params"
    # The docstring from the function:
    assert "async function with no parameters" in tool.description.lower()
    # No required fields, empty properties
    assert tool.input_schema["properties"] == {}
    assert tool.input_schema["required"] == []


def test_custom_name_and_description():
    """You can override the tool name/description in from_callable()."""

    async def foo(bar: Annotated[str, "testing"]):
        """Docstring that should be overridden."""
        return bar

    tool = ToolDefinition.from_callable(
        foo,
        name="my_custom_name",
        description="My custom description",
    )
    assert tool.name == "my_custom_name"
    assert tool.description == "My custom description"


def test_multiline_docstring():
    """Multiline docstring"""

    async def foo(bar: Annotated[str, "testing"]):
        """Docstring line 0
        This is a multiline docstring.
          - item 1
          - item 2
        """
        return bar

    tool = ToolDefinition.from_callable(
        foo,
    )
    assert tool.name == "foo"
    assert (
        tool.description
        == "Docstring line 0\nThis is a multiline docstring.\n  - item 1\n  - item 2"
    )


def test_falls_back_to_docstring():
    """If no description is given, we use the function's docstring."""

    async def a_cool_tool(x: Annotated[int, "testing"]):
        """This is the docstring."""
        return x

    tool = ToolDefinition.from_callable(a_cool_tool)
    assert tool.name == "a_cool_tool"
    assert "This is the docstring." in tool.description


def test_falls_back_to_default_description_if_docstring_empty():
    async def empty_docstring_tool():
        pass

    tool = ToolDefinition.from_callable(empty_docstring_tool)
    # The docstring is empty, so we expect a fallback
    # Something like: "<function name> function."
    assert tool.name == "empty_docstring_tool"
    assert "empty_docstring_tool function." in tool.description


def test_required_vs_optional_no_strict():
    """Parameters with no default are required; with default are optional."""

    async def my_tool(a: Annotated[str, "testing"], b: Annotated[int, "testing"] = 999):
        return a, b

    tool = ToolDefinition.from_callable(my_tool, strict=False)
    schema = tool.input_schema
    assert schema["required"] == ["a"]
    assert "b" not in schema["required"]

    props = schema["properties"]
    assert props["a"]["type"] == "string"
    # b is an int
    assert props["b"]["type"] == "integer"


def test_required_vs_optional_strict():
    """Parameters with no default are required; with default are
    STILL required in strict mode."""

    async def my_tool(a: Annotated[str, "testing"], b: Annotated[int, "testing"] = 999):
        return a, b

    tool = ToolDefinition.from_callable(my_tool, strict=True)
    schema = tool.input_schema
    assert schema["required"] == ["a", "b"]


def test_optional_nullable():
    """Union[str, None] should produce a type of ['string', 'null']."""

    async def my_tool(x: Annotated[str | None, "testing"]):
        """Testing"""
        return x

    tool = ToolDefinition.from_callable(my_tool)
    schema = tool.input_schema
    props = schema["properties"]
    x_schema = props["x"]
    # The param is not in "required" because it has no default? Actually
    # Note that "Optional" alone doesn't mean it has a default.
    # It's "required" if there's no default. It's also "nullable" in the type.
    assert "x" in schema["required"], (
        "Optional without a default is still required, but can be null."
    )
    assert x_schema["type"] == ["string", "null"]


def test_default_optional_nullable():
    """
    If we have a default of None for an Optional field,
    it's not required, plus the schema type is ['string', 'null'].
    """

    async def my_tool(x: Annotated[str | None, "testing"] = None):
        """Testing"""
        return x

    tool = ToolDefinition.from_callable(my_tool, strict=False)
    schema = tool.input_schema
    assert "x" not in schema["required"]
    props = schema["properties"]
    x_schema = props["x"]
    assert x_schema["type"] == ["string", "null"]


def test_annotated_field():
    """Annotated[str, 'some desc'] should yield a string with that description."""

    async def my_tool(value: Annotated[str, "A custom description for 'value'"]):
        """Testing"""
        return value

    tool = ToolDefinition.from_callable(my_tool)
    schema = tool.input_schema
    props = schema["properties"]
    assert props["value"]["type"] == "string"
    assert props["value"]["description"] == "A custom description for 'value'"
    assert schema["required"] == ["value"]  # no default


def test_enum_param():
    """We should produce an enum array for an Enum parameter."""

    async def tool_with_enum(e: Annotated[ExampleEnum, "testing"]):
        """Testing"""
        return e

    tool = ToolDefinition.from_callable(tool_with_enum)
    schema = tool.input_schema
    assert schema["required"] == ["e"]
    e_schema = schema["properties"]["e"]
    assert e_schema["type"] == "string"
    # The enum should have a list of possible values
    assert set(e_schema["enum"]) == {
        "relevance",
        "date",
        "popularity",
        "alphabetical",
    }


def test_enum_param_nullable():
    """Optional enum -> ['string', 'null'] + 'enum' for actual values."""

    async def tool_with_enum(e: Annotated[ExampleEnum | None, "testing"]):
        """Testing"""
        return e

    tool = ToolDefinition.from_callable(tool_with_enum)
    schema = tool.input_schema
    # It's still "required" if there's no default. But can be null at runtime.
    assert schema["required"] == ["e"]
    e_schema = schema["properties"]["e"]
    assert e_schema["type"] == ["string", "null"]
    assert set(e_schema["enum"]) == {
        "relevance",
        "date",
        "popularity",
        "alphabetical",
    }


def test_dataclass_param():
    """A parameter that is a dataclass should produce nested object schema."""

    async def create_person(person: Annotated[PersonData, "testing"]):
        """Testing"""
        return f"Created {person.name} age={person.age}"

    tool = ToolDefinition.from_callable(create_person, strict=False)
    schema = tool.input_schema
    assert "person" in schema["required"]
    assert "strict" not in schema

    person_schema = schema["properties"]["person"]
    assert person_schema["type"] == "object"
    # name is required, age is nullable
    assert "name" in person_schema["required"]
    assert "properties" in person_schema
    assert "name" in person_schema["properties"]
    # age is nullable (so it's required, but can be null)
    assert "age" in person_schema["properties"]
    assert "null" in person_schema["properties"]["age"]["type"]
    # whereas height is truly optional
    assert "height" in person_schema["properties"]
    assert "height" not in person_schema["required"]


def test_dataclass_complex_with_list_and_nested_person():
    """A dataclass with a list and a nested person object."""

    async def create_complex_data(data: ComplexDataWithListAndNestedPerson):
        """Testing"""
        return f"Created {data.person.name} age={data.person.age} with values={data.values}"

    tool = ToolDefinition.from_callable(create_complex_data, strict=False)
    schema = tool.input_schema
    assert "data" in schema["required"]
    assert "strict" not in schema

    complex_schema = schema["properties"]["data"]
    assert complex_schema["type"] == "object"
    assert "person" in complex_schema["required"]
    assert "enum_value" in complex_schema["required"]
    assert "values" not in complex_schema["required"]

    person_schema = complex_schema["properties"]["person"]
    assert person_schema["type"] == "object"
    assert "name" in person_schema["required"]
    assert "null" in person_schema["properties"]["age"]["type"]

    enum_schema = complex_schema["properties"]["enum_value"]
    assert enum_schema["type"] == "string"
    assert enum_schema["enum"] == ["relevance", "date", "popularity", "alphabetical"]

    values_schema = complex_schema["properties"]["values"]
    assert values_schema["type"] == "array"
    assert values_schema["items"]["type"] == "string"


def test_list_of_strings():
    """list[str] => array of string items."""

    async def my_tool(values: Annotated[list[str], "testing"]):
        """Testing"""
        return values

    tool = ToolDefinition.from_callable(my_tool)
    schema = tool.input_schema
    props = schema["properties"]
    v_schema = props["values"]
    assert v_schema["type"] == "array"
    assert v_schema["items"]["type"] == "string"
    assert "values" in schema["required"]


def test_tuple_homogeneous():
    """Tuple[str, ...] => array of string items."""

    async def my_tool(values: Annotated[tuple[str, ...], "testing"]):
        """Testing"""
        return values

    tool = ToolDefinition.from_callable(my_tool)
    schema = tool.input_schema
    props = schema["properties"]
    v_schema = props["values"]
    assert v_schema["type"] == "array"
    assert v_schema["items"]["type"] == "string"


def test_reject_multi_type_tuple():
    """tuple[str, int] => raise an error (not allowed)."""

    async def my_tool(t: Annotated[tuple[str, int], "testing"]):
        """Testing"""
        return t

    with pytest.raises(
        ValueError,
        match="Parameter 't' uses a multi-type or zero-type tuple/list.*",
    ):
        ToolDefinition.from_callable(my_tool)


def test_reject_union_multiple_non_none():
    """Union[str, int] => raise an error (multiple non-None)."""

    async def my_tool(x: Annotated[str | int, "testing"]):
        """Testing"""
        return x

    with pytest.raises(ValueError, match="Parameter 'x' has an unsupported type"):
        ToolDefinition.from_callable(my_tool)


def test_reject_args_kwargs():
    """Functions with *args or **kwargs => raise error."""

    async def tool_with_args(*args: Annotated[str, "testing"]):
        """Testing"""
        pass

    with pytest.raises(ValueError, match="Unsupported parameter kind"):
        ToolDefinition.from_callable(tool_with_args)

    async def tool_with_kwargs(**kwargs: Annotated[str, "testing"]):
        """Testing"""
        pass

    with pytest.raises(ValueError, match="Unsupported parameter kind"):
        ToolDefinition.from_callable(tool_with_kwargs)


def test_strict_flag():
    """Setting strict=True or False should reflect in input_schema."""

    async def my_tool(x: Annotated[str, "testing"]):
        """Testing"""
        return x

    tool_strict = ToolDefinition.from_callable(my_tool, strict=True)
    assert tool_strict.input_schema.get("strict") is True

    tool_not_strict = ToolDefinition.from_callable(my_tool, strict=False)
    assert "strict" not in tool_not_strict.input_schema


def test_unsupported_type():
    class Foo:
        pass

    async def my_tool(x: Annotated[Foo, "testing"]):
        """Testing"""
        return x

    with pytest.raises(ValueError, match="unsupported type"):
        ToolDefinition.from_callable(my_tool)


def test_reject_non_async_function():
    """Non-async functions should raise a ValueError."""

    def not_async(a: Annotated[str, "testing"]):
        """Testing"""
        pass

    with pytest.raises(ValueError, match="must be async"):
        ToolDefinition.from_callable(
            not_async,  # type: ignore (testing invalid usage)
        )
