import json
import os
from unittest.mock import patch

import pytest

from agent_platform.core.actions.action_utils import (
    _dereference_refs,
    get_spec_and_build_tool_definitions,
)


class MockResponse:
    def __init__(self, data):
        self.data = data

    async def json(self):
        return self.data

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class MockClientSession:
    def __init__(self, response_data):
        self.response_data = response_data

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

    def get(self, url, **kwargs):
        return MockResponse(self.response_data)

    def post(self, url, **kwargs):
        return MockResponse({"result": "success"})


@pytest.fixture
def sample_openapi_spec():
    """Loads a sample OpenAPI spec rendered from an actual action server."""
    example_path = os.path.join(
        os.path.dirname(__file__),
        "example-action-server-spec.json",
    )
    with open(example_path) as f:
        return json.load(f)


@pytest.mark.asyncio
@patch("aiohttp.ClientSession")
async def test_get_spec_and_build_definitions(mock_client_session, sample_openapi_spec):
    """Test fetching OpenAPI spec and building tool definitions."""
    # Setup mock
    mock_session = MockClientSession(sample_openapi_spec)
    mock_client_session.return_value = mock_session

    # Call function
    tool_definitions = await get_spec_and_build_tool_definitions(
        "http://localhost:8083",
        "test-api-key",
        [],  # No filter, all actions allowed
    )

    # Assertions
    assert len(tool_definitions) == 3
    assert tool_definitions[0].name == "serpapi_google_search_streamlined"
    assert tool_definitions[0].description == (
        "Perform a streamlined Google search using SerpApi. Returns organic "
        "results and local map places only.\nExcludes sponsored listings, "
        'product ads, and other "noise".'
    )
    assert tool_definitions[0].input_schema["properties"]["query"]["type"] == "string"
    assert tool_definitions[0].input_schema["required"] == ["query"]

    assert tool_definitions[1].name == "serpapi_geocode_place_name"
    assert tool_definitions[1].description == (
        "Perform a geocoding search using SerpApi, returning GPS coordinates for a place name."
    )
    assert tool_definitions[1].input_schema["properties"]["place_name"]["type"] == "string"
    assert tool_definitions[1].input_schema["required"] == ["place_name"]

    assert tool_definitions[2].name == "serpapi_google_map_search"
    assert tool_definitions[2].description == (
        "Perform a Google Maps (local) search using SerpApi, returning typed "
        "local/map results.\nYou must give a latitude and longitude for the search "
        "location. If you are uncertain\nyou can FIRST use the GEOCODING API to "
        "get the coordinates for a place name."
    )
    assert tool_definitions[2].input_schema["properties"]["query"]["type"] == "string"
    assert tool_definitions[2].input_schema["required"] == [
        "query",
        "latitude",
        "longitude",
    ]


@pytest.mark.asyncio
@patch("aiohttp.ClientSession")
async def test_get_spec_with_allowed_actions_filter(mock_client_session, sample_openapi_spec):
    """Test filtering actions by allowed_actions."""
    # Setup mock
    mock_session = MockClientSession(sample_openapi_spec)
    mock_client_session.return_value = mock_session

    # Call function with filter
    tool_definitions = await get_spec_and_build_tool_definitions(
        "http://localhost:8083",
        "test-api-key",
        ["serpapi_doesnt_exist"],  # This doesn't match our testAction
    )

    # Assertions - should be empty since our filter doesn't match
    assert len(tool_definitions) == 0


@pytest.mark.asyncio
@patch("aiohttp.ClientSession")
async def test_get_spec_with_one_action(mock_client_session, sample_openapi_spec):
    """Test handling of missing URL."""
    # Setup mock
    mock_session = MockClientSession(sample_openapi_spec)
    mock_client_session.return_value = mock_session

    # Call function
    tool_definitions = await get_spec_and_build_tool_definitions(
        "http://localhost:8083",
        "test-api-key",
        ["serpapi_google_search_streamlined"],
    )

    # Assertions
    assert len(tool_definitions) == 1
    assert tool_definitions[0].name == "serpapi_google_search_streamlined"
    assert tool_definitions[0].description == (
        "Perform a streamlined Google search using SerpApi. Returns organic "
        "results and local map places only.\nExcludes sponsored listings, "
        'product ads, and other "noise".'
    )
    assert tool_definitions[0].input_schema["properties"]["query"]["type"] == "string"
    assert tool_definitions[0].input_schema["required"] == ["query"]


def test_dereference_refs():
    """Test dereferencing JSON schema references."""
    # Sample schema with references
    schema = {
        "components": {
            "schemas": {
                "TestObject": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                }
            }
        }
    }

    # Spec with a reference
    spec = {"param1": {"$ref": "components/schemas/TestObject"}}

    # Dereference
    result = _dereference_refs(spec, schema)

    # Assertions
    assert "$ref" not in result["param1"]
    assert result["param1"]["type"] == "object"
    assert result["param1"]["properties"]["name"]["type"] == "string"


def test_dereference_nested_refs():
    """Test dereferencing nested JSON schema references."""
    schema = {
        "components": {
            "schemas": {
                "NestedObject": {"type": "string", "description": "A nested string"},
                "ParentObject": {
                    "type": "object",
                    "properties": {"nested": {"$ref": "#/components/schemas/NestedObject"}},
                },
            }
        }
    }
    spec = {"topLevel": {"$ref": "#/components/schemas/ParentObject"}}
    result = _dereference_refs(spec, schema)

    assert "$ref" not in result["topLevel"]
    assert result["topLevel"]["type"] == "object"
    assert "$ref" not in result["topLevel"]["properties"]["nested"]
    assert result["topLevel"]["properties"]["nested"]["type"] == "string"
    assert result["topLevel"]["properties"]["nested"]["description"] == "A nested string"


def test_dereference_ref_in_list():
    """Test dereferencing a reference within a list."""
    schema = {"components": {"schemas": {"SimpleString": {"type": "string", "example": "hello"}}}}
    spec = {"listOfStrings": [{"$ref": "#/components/schemas/SimpleString"}]}
    result = _dereference_refs(spec, schema)

    assert isinstance(result["listOfStrings"], list)
    assert len(result["listOfStrings"]) == 1
    assert "$ref" not in result["listOfStrings"][0]
    assert result["listOfStrings"][0]["type"] == "string"
    assert result["listOfStrings"][0]["example"] == "hello"


def test_dereference_ref_to_primitive():
    """Test dereferencing a reference that points directly to a primitive type."""
    schema = {"components": {"schemas": {"MyStringType": {"type": "string"}}}}
    spec = {"primitiveRef": {"$ref": "#/components/schemas/MyStringType"}}
    result = _dereference_refs(spec, schema)

    # The resolved value replaces the object containing the $ref
    assert result["primitiveRef"]["type"] == "string"


def test_dereference_ref_with_sibling_keys():
    """Test that sibling keys next to a $ref are ignored
    (replaced by resolved value)."""
    schema = {
        "components": {
            "schemas": {
                "TargetObject": {
                    "type": "object",
                    "properties": {"a": {"type": "integer"}},
                }
            }
        }
    }
    spec = {
        "refWithSibling": {
            "$ref": "#/components/schemas/TargetObject",
            "description": "This should be ignored",  # Sibling key
        }
    }
    result = _dereference_refs(spec, schema)

    assert "description" not in result["refWithSibling"]  # Sibling key is gone
    assert result["refWithSibling"]["type"] == "object"
    assert result["refWithSibling"]["properties"]["a"]["type"] == "integer"


def test_dereference_unresolvable_ref():
    """Test handling of an unresolvable reference
    (should ideally log warning and skip)."""
    schema = {"components": {"schemas": {}}}  # Empty schemas
    spec = {"badRef": {"$ref": "#/components/schemas/DoesNotExist"}}

    # Expect the original structure with the unresolved ref to be returned
    # (The function logs a warning but doesn't raise an error)
    result = _dereference_refs(spec, schema)

    assert "$ref" in result["badRef"]
    assert result["badRef"]["$ref"] == "#/components/schemas/DoesNotExist"


def test_dereference_relative_ref_format():
    """Test dereferencing using the relative path format."""
    schema = {
        "components": {
            "schemas": {
                "TestObject": {
                    "type": "object",
                    "properties": {"name": {"type": "string"}},
                }
            }
        }
    }
    # Reference without leading '#/'
    spec = {"param1": {"$ref": "components/schemas/TestObject"}}
    result = _dereference_refs(spec, schema)

    assert "$ref" not in result["param1"]
    assert result["param1"]["type"] == "object"
    assert result["param1"]["properties"]["name"]["type"] == "string"


@pytest.mark.asyncio
@patch("aiohttp.ClientSession")
async def test_request_body_schema_with_complex_nested_structure(mock_client_session):
    """Test that complex nested request body schemas are preserved properly."""
    complex_spec = {
        "openapi": "3.1.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/api/actions/test-complex-schema/run": {
                "post": {
                    "operationId": "test_complex_schema",
                    "description": "Test action with complex schema",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "user_info": {
                                            "type": "object",
                                            "properties": {
                                                "name": {"type": "string"},
                                                "age": {"type": "integer", "minimum": 0},
                                                "email": {
                                                    "type": "string",
                                                    "format": "email",
                                                    "default": "user@example.com",
                                                },
                                            },
                                            "required": ["name", "age"],
                                        },
                                        "preferences": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "category": {"type": "string"},
                                                    "value": {
                                                        "anyOf": [
                                                            {"type": "string"},
                                                            {"type": "number"},
                                                            {"type": "boolean"},
                                                        ]
                                                    },
                                                },
                                            },
                                        },
                                        "mode": {
                                            "type": "string",
                                            "enum": ["basic", "advanced"],
                                            "default": "basic",
                                        },
                                    },
                                    "required": ["user_info"],
                                }
                            }
                        }
                    },
                    "responses": {"200": {"description": "Success"}},
                }
            }
        },
    }

    mock_session = MockClientSession(complex_spec)
    mock_client_session.return_value = mock_session

    tool_definitions = await get_spec_and_build_tool_definitions(
        "http://localhost:8083", "test-api-key", []
    )

    assert len(tool_definitions) == 1
    tool = tool_definitions[0]

    # Verify the complex nested structure is preserved
    user_info_schema = tool.input_schema["properties"]["user_info"]
    assert user_info_schema["type"] == "object"
    assert user_info_schema["properties"]["name"]["type"] == "string"
    assert user_info_schema["properties"]["age"]["type"] == "integer"
    assert user_info_schema["properties"]["age"]["minimum"] == 0
    assert user_info_schema["properties"]["email"]["default"] == "user@example.com"
    assert user_info_schema["properties"]["email"]["format"] == "email"
    assert user_info_schema["required"] == ["name", "age"]

    # Verify array with complex items schema
    preferences_schema = tool.input_schema["properties"]["preferences"]
    assert preferences_schema["type"] == "array"
    assert preferences_schema["items"]["type"] == "object"
    assert preferences_schema["items"]["properties"]["category"]["type"] == "string"

    # Verify anyOf is preserved
    value_schema = preferences_schema["items"]["properties"]["value"]
    assert "anyOf" in value_schema
    assert len(value_schema["anyOf"]) == 3
    assert {"type": "string"} in value_schema["anyOf"]
    assert {"type": "number"} in value_schema["anyOf"]
    assert {"type": "boolean"} in value_schema["anyOf"]

    # Verify enum and default are preserved
    mode_schema = tool.input_schema["properties"]["mode"]
    assert mode_schema["type"] == "string"
    assert mode_schema["enum"] == ["basic", "advanced"]
    assert mode_schema["default"] == "basic"

    # Verify top-level required
    assert tool.input_schema["required"] == ["user_info"]


@pytest.mark.asyncio
@patch("aiohttp.ClientSession")
async def test_request_body_schema_with_refs(mock_client_session):
    """Test that request body schemas with $ref references are properly dereferenced."""
    spec_with_refs = {
        "openapi": "3.1.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "components": {
            "schemas": {
                "UserInfo": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "contact": {"$ref": "#/components/schemas/ContactInfo"},
                    },
                    "required": ["name"],
                },
                "ContactInfo": {
                    "type": "object",
                    "properties": {
                        "email": {"type": "string", "format": "email"},
                        "phone": {"type": "string", "pattern": "^\\+?[1-9]\\d{1,14}$"},
                    },
                },
            }
        },
        "paths": {
            "/api/actions/test-refs/run": {
                "post": {
                    "operationId": "test_refs",
                    "description": "Test action with schema references",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "user": {"$ref": "#/components/schemas/UserInfo"},
                                        "metadata": {
                                            "type": "object",
                                            "properties": {
                                                "source": {"type": "string"},
                                                "nested_contact": {
                                                    "$ref": "#/components/schemas/ContactInfo"
                                                },
                                            },
                                        },
                                    },
                                    "required": ["user"],
                                }
                            }
                        }
                    },
                    "responses": {"200": {"description": "Success"}},
                }
            }
        },
    }

    mock_session = MockClientSession(spec_with_refs)
    mock_client_session.return_value = mock_session

    tool_definitions = await get_spec_and_build_tool_definitions(
        "http://localhost:8083", "test-api-key", []
    )

    assert len(tool_definitions) == 1
    tool = tool_definitions[0]

    # Verify that $ref was dereferenced in the user property
    user_schema = tool.input_schema["properties"]["user"]
    assert "$ref" not in user_schema
    assert user_schema["type"] == "object"
    assert user_schema["properties"]["name"]["type"] == "string"
    assert user_schema["required"] == ["name"]

    # Verify nested $ref was dereferenced
    contact_schema = user_schema["properties"]["contact"]
    assert "$ref" not in contact_schema
    assert contact_schema["type"] == "object"
    assert contact_schema["properties"]["email"]["type"] == "string"
    assert contact_schema["properties"]["email"]["format"] == "email"
    assert contact_schema["properties"]["phone"]["pattern"] == "^\\+?[1-9]\\d{1,14}$"

    # Verify nested $ref in metadata was also dereferenced
    metadata_schema = tool.input_schema["properties"]["metadata"]
    nested_contact_schema = metadata_schema["properties"]["nested_contact"]
    assert "$ref" not in nested_contact_schema
    assert nested_contact_schema["type"] == "object"
    assert nested_contact_schema["properties"]["email"]["type"] == "string"

    # Verify top-level required is preserved
    assert tool.input_schema["required"] == ["user"]


@pytest.mark.asyncio
@patch("aiohttp.ClientSession")
async def test_request_body_schema_preserves_all_json_schema_features(mock_client_session):
    """Test that all JSON Schema features are preserved in request body schema extraction."""
    comprehensive_spec = {
        "openapi": "3.1.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/api/actions/comprehensive-schema/run": {
                "post": {
                    "operationId": "comprehensive_schema",
                    "description": "Test comprehensive JSON Schema features",
                    "requestBody": {
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "string_with_constraints": {
                                            "type": "string",
                                            "minLength": 5,
                                            "maxLength": 100,
                                            "pattern": "^[A-Za-z0-9]+$",
                                            "title": "String Field",
                                            "description": "A string with various constraints",
                                        },
                                        "number_with_constraints": {
                                            "type": "number",
                                            "minimum": 0,
                                            "maximum": 999.99,
                                            "multipleOf": 0.01,
                                            "default": 10.5,
                                        },
                                        "conditional_field": {
                                            "oneOf": [
                                                {"type": "string", "enum": ["option1", "option2"]},
                                                {"type": "integer", "minimum": 1},
                                            ]
                                        },
                                        "array_with_unique_items": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                            "uniqueItems": True,
                                            "minItems": 1,
                                            "maxItems": 10,
                                        },
                                        "const_field": {"const": "fixed_value"},
                                    },
                                    "required": ["string_with_constraints", "conditional_field"],
                                    "additionalProperties": False,
                                }
                            }
                        }
                    },
                    "responses": {"200": {"description": "Success"}},
                }
            }
        },
    }

    mock_session = MockClientSession(comprehensive_spec)
    mock_client_session.return_value = mock_session

    tool_definitions = await get_spec_and_build_tool_definitions(
        "http://localhost:8083", "test-api-key", []
    )

    assert len(tool_definitions) == 1
    tool = tool_definitions[0]

    # Verify string constraints are preserved
    string_field = tool.input_schema["properties"]["string_with_constraints"]
    assert string_field["minLength"] == 5
    assert string_field["maxLength"] == 100
    assert string_field["pattern"] == "^[A-Za-z0-9]+$"
    assert string_field["title"] == "String Field"
    assert string_field["description"] == "A string with various constraints"

    # Verify number constraints are preserved
    number_field = tool.input_schema["properties"]["number_with_constraints"]
    assert number_field["minimum"] == 0
    assert number_field["maximum"] == 999.99
    assert number_field["multipleOf"] == 0.01
    assert number_field["default"] == 10.5

    # Verify oneOf is preserved
    conditional_field = tool.input_schema["properties"]["conditional_field"]
    assert "oneOf" in conditional_field
    assert len(conditional_field["oneOf"]) == 2

    # Verify array constraints are preserved
    array_field = tool.input_schema["properties"]["array_with_unique_items"]
    assert array_field["uniqueItems"] is True
    assert array_field["minItems"] == 1
    assert array_field["maxItems"] == 10

    # Verify const is preserved
    const_field = tool.input_schema["properties"]["const_field"]
    assert const_field["const"] == "fixed_value"

    # Verify schema-level properties are preserved
    assert tool.input_schema["required"] == ["string_with_constraints", "conditional_field"]


@pytest.mark.asyncio
@patch("aiohttp.ClientSession")
async def test_request_body_schema_empty_or_missing(mock_client_session):
    """Test handling of actions with empty or missing request body schemas."""
    minimal_spec = {
        "openapi": "3.1.0",
        "info": {"title": "Test API", "version": "1.0.0"},
        "paths": {
            "/api/actions/no-request-body/run": {
                "post": {
                    "operationId": "no_request_body",
                    "description": "Test action with no request body",
                    "responses": {"200": {"description": "Success"}},
                }
            },
            "/api/actions/empty-schema/run": {
                "post": {
                    "operationId": "empty_schema",
                    "description": "Test action with empty schema",
                    "requestBody": {"content": {"application/json": {"schema": {}}}},
                    "responses": {"200": {"description": "Success"}},
                }
            },
        },
    }

    mock_session = MockClientSession(minimal_spec)
    mock_client_session.return_value = mock_session

    tool_definitions = await get_spec_and_build_tool_definitions(
        "http://localhost:8083", "test-api-key", []
    )

    assert len(tool_definitions) == 2

    # Test action with no request body
    no_body_tool = next(t for t in tool_definitions if t.name == "no_request_body")
    assert no_body_tool.input_schema["properties"] == {}
    assert no_body_tool.input_schema["required"] == []

    # Test action with empty schema
    empty_schema_tool = next(t for t in tool_definitions if t.name == "empty_schema")
    assert empty_schema_tool.input_schema["properties"] == {}
    assert empty_schema_tool.input_schema["required"] == []
