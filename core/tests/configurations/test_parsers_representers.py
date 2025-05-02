"""Unit tests for configuration parsers and representers."""

import enum
import io
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, ClassVar, Literal

import pytest
import yaml

from agent_platform.core.configurations import (
    AstParserMixin,
    BoolParser,
    Configuration,
    EnumParser,
    FieldMetadata,
    FloatParser,
    IntParser,
    LiteralParser,
    NestedListParser,
    NestedMappingParser,
    PathParser,
    PathRepresenter,
    StrParser,
    get_parser_for_field,
    get_representer_for_field,
    is_union_of_dataclasses_type,
    parse_field_value,
    represent_field_value,
)
from agent_platform.core.configurations.errors import ConfigurationDiscriminatorError
from agent_platform.core.configurations.parsers import Parser


class TestBasicParsers:
    """Tests for the basic parser classes."""

    def test_str_parser(self) -> None:
        """Test the StrParser."""
        parser = StrParser()
        assert parser.parse("test") == "test"
        assert parser.parse(123) == "123"
        assert parser.parse(True) == "True"

    def test_int_parser(self) -> None:
        """Test the IntParser."""
        parser = IntParser()
        assert parser.parse("123") == 123
        assert parser.parse(123) == 123

        # Test invalid conversion
        with pytest.raises(
            ValueError,
            match=r"invalid literal for int\(\) with base 10: 'not an int'",
        ):
            parser.parse("not an int")

    def test_float_parser(self) -> None:
        """Test the FloatParser."""
        parser = FloatParser()
        assert parser.parse("123.45") == 123.45
        assert parser.parse(123.45) == 123.45
        assert parser.parse("123") == 123.0

        # Test invalid conversion
        with pytest.raises(
            ValueError,
            match="could not convert string to float: 'not a float'",
        ):
            parser.parse("not a float")

    def test_bool_parser(self) -> None:
        """Test the BoolParser."""
        parser = BoolParser()
        # Test string values
        assert parser.parse("true") is True
        assert parser.parse("True") is True
        assert parser.parse("t") is True
        assert parser.parse("yes") is True
        assert parser.parse("y") is True
        assert parser.parse("1") is True
        assert parser.parse("false") is False
        assert parser.parse("False") is False
        assert parser.parse("f") is False
        assert parser.parse("no") is False
        assert parser.parse("n") is False
        assert parser.parse("0") is False

        # Test boolean values
        assert parser.parse(True) is True
        assert parser.parse(False) is False

        # Test integer values
        assert parser.parse(1) is True
        assert parser.parse(0) is False

        # Test invalid conversion
        with pytest.raises(
            ValueError,
            match="Value is not a boolean: {'not': 'a bool'}",
        ):
            parser.parse({"not": "a bool"})

    def test_path_parser(self) -> None:
        """Test the PathParser."""
        parser = PathParser()

        # Test string conversion
        assert parser.parse("/path/to/file") == Path("/path/to/file")
        assert parser.parse("relative/path") == Path("relative/path")

        # Test Path object
        path = Path("/path/to/file")
        assert parser.parse(str(path)) == path

        # Test invalid conversion
        with pytest.raises(
            ValueError,
            match="Value is not a path: 123",
        ):
            parser.parse(123)  # Int isn't a valid path


class TestComplexParsers:
    """Tests for the more complex parser classes."""

    def test_literal_parser(self) -> None:
        """Test the LiteralParser."""

        # Create a field with a Literal type
        @dataclass
        class TestConfig:
            mode: Literal["test", "dev", "prod"] = "dev"

        # Get the field and create a parser
        field = TestConfig.__dataclass_fields__["mode"]
        parser = LiteralParser(field)

        # Test valid values
        assert parser.parse("test") == "test"
        assert parser.parse("dev") == "dev"
        assert parser.parse("prod") == "prod"

        # Test invalid value
        with pytest.raises(
            ValueError,
            match=r"Failed to parse Literal value 'invalid': Value 'invalid' is not "
            r"one of the allowed options: \('test', 'dev', 'prod'\)",
        ):
            parser.parse("invalid")

    def test_enum_parser(self) -> None:
        """Test the EnumParser."""

        # Create an enum and a field with the enum type
        class Color(enum.Enum):
            RED = "red"
            GREEN = "green"
            BLUE = "blue"

        @dataclass
        class TestConfig:
            color: Color = Color.RED

        # Get the field and create a parser
        field = TestConfig.__dataclass_fields__["color"]
        parser = EnumParser(field)

        # Test valid values
        assert parser.parse("red") == Color.RED
        assert parser.parse("green") == Color.GREEN
        assert parser.parse("blue") == Color.BLUE

        # Test invalid values
        with pytest.raises(
            ValueError,
            match="Failed to parse value 'yellow' into enum Color",
        ):
            parser.parse("yellow")

        # Test with value not initialized with a field
        parser_no_field = EnumParser()
        with pytest.raises(
            ValueError,
            match="EnumParser must be initialized with a Field",
        ):
            parser_no_field.parse("red")

    def test_nested_list_parser(self) -> None:
        """Test the NestedListParser."""
        parser = NestedListParser()

        # Test basic list
        assert parser.parse("[1, 2, 3]") == [1, 2, 3]

        # Test nested list
        assert parser.parse("[1, [2, 3], 4]") == [1, [2, 3], 4]

        # Test with existing list
        assert parser.parse([1, 2, 3]) == [1, 2, 3]

        # Test with mixed types
        assert parser.parse("[1, 'two', 3.0]") == [1, "two", 3.0]

        # Test with tuple
        assert parser.parse("(1, 2, 3)") == (1, 2, 3)

        # Test with set
        result = parser.parse("{1, 2, 3}")
        assert result is not None
        assert set(result) == {1, 2, 3}

        # Test with invalid string
        with pytest.raises(
            ValueError,
            match="Failed to parse sequence value: not a list",
        ):
            parser.parse("not a list")

    def test_nested_mapping_parser(self) -> None:
        """Test the NestedMappingParser."""
        parser = NestedMappingParser()

        # Test basic dict
        assert parser.parse("{'a': 1, 'b': 2}") == {"a": 1, "b": 2}

        # Test nested dict
        assert parser.parse("{'a': 1, 'b': {'c': 3}}") == {"a": 1, "b": {"c": 3}}

        # Test with existing dict
        assert parser.parse({"a": 1, "b": 2}) == {"a": 1, "b": 2}

        # Test with mixed types
        assert parser.parse("{'a': 1, 'b': 'two', 'c': 3.0}") == {
            "a": 1,
            "b": "two",
            "c": 3.0,
        }

        # Test with nested list in dict
        assert parser.parse("{'a': 1, 'b': [2, 3, 4]}") == {"a": 1, "b": [2, 3, 4]}

        # Test with invalid string
        with pytest.raises(
            ValueError,
            match="Failed to parse mapping value: not a dict",
        ):
            parser.parse("not a dict")

    def test_ast_parser_mixin(self) -> None:
        """Test the AstParserMixin."""

        class TestParser(AstParserMixin, Parser):
            _supported_types: ClassVar[set[Any]] = {dict}

            def parse(self, value: Any) -> Any:
                return self.literal_eval(value)

        parser = TestParser()

        # Test with valid Python literal
        assert parser.literal_eval("[1, 2, 3]") == [1, 2, 3]
        assert parser.literal_eval("{'a': 1, 'b': 2}") == {"a": 1, "b": 2}

        # Test with expected_types
        assert parser.literal_eval("[1, 2, 3]", (list,)) == [1, 2, 3]

        # Test with wrong expected_types
        with pytest.raises(ValueError, match=r"Failed to parse value: \[1, 2, 3\]"):
            parser.literal_eval("[1, 2, 3]", (dict,))

        # Test with invalid Python literal
        with pytest.raises(ValueError, match="Failed to parse value: import os"):
            parser.literal_eval("import os")


class TestParserUtilities:
    """Tests for parser utility functions."""

    def test_get_parser_for_field(self) -> None:
        """Test get_parser_for_field function."""

        @dataclass
        class TestConfig:
            string: str = "test"
            integer: int = 123
            flag: bool = True
            path: Path = Path("/path")
            options: Literal["a", "b", "c"] = "a"
            nested_list: list[int] = field(default_factory=list)
            nested_dict: dict[str, Any] = field(default_factory=dict)

        # Test basic types
        string_field = TestConfig.__dataclass_fields__["string"]
        assert isinstance(get_parser_for_field(string_field), StrParser)

        integer_field = TestConfig.__dataclass_fields__["integer"]
        assert isinstance(get_parser_for_field(integer_field), IntParser)

        bool_field = TestConfig.__dataclass_fields__["flag"]
        assert isinstance(get_parser_for_field(bool_field), BoolParser)

        path_field = TestConfig.__dataclass_fields__["path"]
        assert isinstance(get_parser_for_field(path_field), PathParser)

        # Test complex types
        literal_field = TestConfig.__dataclass_fields__["options"]
        assert isinstance(get_parser_for_field(literal_field), LiteralParser)

        list_field = TestConfig.__dataclass_fields__["nested_list"]
        assert isinstance(get_parser_for_field(list_field), NestedListParser)

        dict_field = TestConfig.__dataclass_fields__["nested_dict"]
        assert isinstance(get_parser_for_field(dict_field), NestedMappingParser)

    def test_parse_field_value(self) -> None:
        """Test parse_field_value function."""

        @dataclass
        class TestConfig:
            string: str = "test"
            integer: int = 123
            flag: bool = True
            path: Path = Path("/path")

        # Test string field
        string_field = TestConfig.__dataclass_fields__["string"]
        assert parse_field_value(string_field, "new string") == "new string"
        assert parse_field_value(string_field, 123) == "123"

        # Test integer field
        integer_field = TestConfig.__dataclass_fields__["integer"]
        assert parse_field_value(integer_field, "456") == 456
        assert parse_field_value(integer_field, 456) == 456

        # Test boolean field
        bool_field = TestConfig.__dataclass_fields__["flag"]
        assert parse_field_value(bool_field, "true") is True
        assert parse_field_value(bool_field, "false") is False
        assert parse_field_value(bool_field, True) is True

        # Test path field
        path_field = TestConfig.__dataclass_fields__["path"]
        assert parse_field_value(path_field, "/new/path") == Path("/new/path")

        # Test with custom parser in metadata
        class CustomParser(Parser):
            _supported_types: ClassVar[set[Any]] = {str}

            def parse(self, value: Any) -> str:
                return f"CUSTOM:{value}"

        @dataclass
        class ConfigWithCustomParser:
            name: str = field(
                default="test",
                metadata={"parser": CustomParser()},
            )

        custom_field = ConfigWithCustomParser.__dataclass_fields__["name"]
        assert parse_field_value(custom_field, "value") == "CUSTOM:value"


class TestRepresenters:
    """Tests for representer classes and utilities."""

    def test_path_representer(self) -> None:
        """Test the PathRepresenter."""
        # Register the representer
        PathRepresenter.register_representer()

        # Test dumping a Path object
        test_path = Path("/path/to/file")
        yaml_str = yaml.dump({"path": test_path})

        # Parse it back and verify
        loaded = yaml.safe_load(yaml_str)
        assert loaded["path"] == str(test_path)

    def test_get_representer_for_field(self) -> None:
        """Test get_representer_for_field function."""

        @dataclass
        class TestConfig:
            path: Path = Path("/path")

        path_field = TestConfig.__dataclass_fields__["path"]
        assert get_representer_for_field(path_field) == PathRepresenter

        # Test with custom representer in metadata
        class CustomRepresenter(PathRepresenter):
            pass

        @dataclass
        class ConfigWithCustomRepresenter:
            path: Path = field(
                default=Path("/path"),
                metadata={"representer": CustomRepresenter},
            )

        custom_field = ConfigWithCustomRepresenter.__dataclass_fields__["path"]
        assert get_representer_for_field(custom_field) == CustomRepresenter

    def test_represent_field_value(self) -> None:
        """Test represent_field_value function."""

        @dataclass
        class TestConfig:
            path: Path = Path("/path")

        path_field = TestConfig.__dataclass_fields__["path"]
        dumper = yaml.dumper.Dumper(io.StringIO())

        # Register the representer
        PathRepresenter.register_representer()

        # Test the function
        result = represent_field_value(path_field, dumper, Path("/test/path"))
        assert result is not None


class TestUnionTypeHandling:
    """Tests for union type handling and related utilities."""

    def test_is_union_of_dataclasses_type(self) -> None:
        """Test the is_union_of_dataclasses_type function."""

        @dataclass
        class ConfigA:
            type: Literal["a"] = "a"
            value: str = ""

        @dataclass
        class ConfigB:
            type: Literal["b"] = "b"
            value: int = 0

        # Test valid union types
        assert is_union_of_dataclasses_type(ConfigA | ConfigB)
        assert is_union_of_dataclasses_type(ConfigA | None)
        assert is_union_of_dataclasses_type(ConfigA | ConfigB | None)

        # Test invalid union types
        assert not is_union_of_dataclasses_type(str | int)
        assert not is_union_of_dataclasses_type(ConfigA | str)
        assert not is_union_of_dataclasses_type(list[ConfigA])

    def test_union_of_dataclass_parser(self) -> None:
        """Test the UnionOfDataclassParser."""
        from agent_platform.core.configurations.parsers import UnionOfDataclassParser

        @dataclass
        class ConfigA:
            value: str = ""

        @dataclass
        class ConfigB:
            value: int = 0

        @dataclass(frozen=True)
        class ParentConfig(Configuration):
            type: Literal["a", "b"] = "a"
            union_field: ConfigA | ConfigB = field(
                default_factory=ConfigA,
                metadata=FieldMetadata(
                    description="A union field that can be either ConfigA or ConfigB",
                    discriminator="type",
                    discriminator_mapping={
                        "a": ConfigA,
                        "b": ConfigB,
                    },
                ),
            )

        # Test parsing ConfigA
        config_a = {"value": "test"}
        parser = UnionOfDataclassParser(
            field=fields(ParentConfig)[1],  # union_field is the second field
            parent_config=ParentConfig(),
        )
        result = parser.parse(config_a)
        assert isinstance(result, ConfigA)
        assert result.value == "test"

        # Test parsing ConfigB
        config_b = {"value": 42}
        parent_config = ParentConfig(type="b")  # Create new instance with type="b"
        parser = UnionOfDataclassParser(
            field=fields(ParentConfig)[1],  # union_field is the second field
            parent_config=parent_config,
        )
        result = parser.parse(config_b)
        assert isinstance(result, ConfigB)
        assert result.value == 42

        # Test invalid discriminator value
        invalid_parser = UnionOfDataclassParser(
            field=fields(ParentConfig)[1],  # union_field is the second field
            parent_config=ParentConfig(
                type="b"
            ),  # Valid literal but invalid for the test case
        )
        with pytest.raises(
            ConfigurationDiscriminatorError,
            match="Failed to create instance of ConfigB",
        ):
            invalid_parser.parse(
                {"value": "test"}
            )  # This will fail because ConfigB expects an int

        # Test missing metadata
        @dataclass(frozen=True)
        class ParentConfigWithoutMetadata(Configuration):
            type: Literal["a", "b"] = "a"
            union_field: ConfigA | ConfigB = field(
                default_factory=ConfigA,
                metadata=FieldMetadata(
                    description="A union field that can be either ConfigA or ConfigB",
                ),
            )

        missing_metadata_parser = UnionOfDataclassParser(
            field=fields(ParentConfigWithoutMetadata)[
                1
            ],  # union_field is the second field
            parent_config=ParentConfigWithoutMetadata(),
        )
        with pytest.raises(
            ConfigurationDiscriminatorError,
            match="Discriminator mapping and discriminator field name are required",
        ):
            missing_metadata_parser.parse({"value": "test"})
