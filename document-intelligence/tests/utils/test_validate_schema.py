import jsonschema
import pytest

from sema4ai_docint.utils import validate_extraction_schema


def test_validate_valid_object_schema():
    """Test that a valid object schema is accepted."""
    schema = """
    {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "number"}
        },
        "required": ["name", "age"]
    }
    """
    result = validate_extraction_schema(schema)
    assert result is not None
    assert result["type"] == "object"
    assert result["properties"] == {
        "name": {"type": "string"},
        "age": {"type": "number"},
    }


def test_validate_complex_valid_object_schema():
    """Test that a complex valid object schema is accepted."""
    schema = """
    {
        "type": "object",
        "properties": {
            "user": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                    "email": {"type": "string", "format": "email"}
                },
                "required": ["id", "name"]
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"}
            },
            "active": {"type": "boolean"}
        },
        "required": ["user"],
        "additionalProperties": false
    }
    """
    result = validate_extraction_schema(schema)
    assert result is not None
    assert result["type"] == "object"
    assert "user" in result["properties"]
    assert result["properties"]["user"]["type"] == "object"


def test_validate_minimal_valid_schema():
    """Test that minimal valid schema (empty properties) is accepted."""
    schema = {"type": "object", "properties": {}}
    result = validate_extraction_schema(schema)
    assert result is not None
    assert result["type"] == "object"
    assert result["properties"] == {}


@pytest.mark.parametrize(
    ("schema", "expected_error"),
    [
        # Invalid JSON Schema structure
        ({"type": "invalid_type", "properties": {}}, jsonschema.exceptions.SchemaError),
        ({"type": None, "properties": {}}, jsonschema.exceptions.SchemaError),
        (
            {"type": "object", "properties": {}, "required": "not a list"},
            jsonschema.exceptions.SchemaError,
        ),
        ({"properties": None, "type": "object"}, jsonschema.exceptions.SchemaError),
        (
            {"properties": ["not", "dict"], "type": "object"},
            jsonschema.exceptions.SchemaError,
        ),
        (
            {"properties": "not dict", "type": "object"},
            jsonschema.exceptions.SchemaError,
        ),
    ],
)
def test_validate_invalid_schema_structure(schema, expected_error):
    """Test that structurally invalid schemas are rejected by metaschema validation."""
    with pytest.raises(expected_error):
        validate_extraction_schema(schema)


@pytest.mark.parametrize(
    "schema",
    [
        {"type": "string"},  # Wrong type
        {"type": "array", "items": {"type": "string"}},  # Array type
        {"type": "number"},  # Number type
        {"properties": {"name": {"type": "string"}}},  # Missing type
    ],
)
def test_validate_non_object_type_schemas(schema):
    """Test that schemas with non-object types are rejected for Reducto compatibility."""
    with pytest.raises(
        ValueError,
        match="Schema must be of type 'object', got type",
    ):
        validate_extraction_schema(schema)


def test_validate_schema_without_properties():
    """Test that schema without properties field is rejected for Reducto compatibility."""
    schema = {"type": "object"}
    with pytest.raises(
        ValueError,
        match="Schema must have a non-null 'properties' field of type 'object'",
    ):
        validate_extraction_schema(schema)
