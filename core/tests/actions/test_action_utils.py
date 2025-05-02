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
        "Perform a geocoding search using SerpApi, returning GPS coordinates "
        "for a place name."
    )
    assert (
        tool_definitions[1].input_schema["properties"]["place_name"]["type"] == "string"
    )
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
async def test_get_spec_with_allowed_actions_filter(
    mock_client_session, sample_openapi_spec
):
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
                    "properties": {
                        "nested": {"$ref": "#/components/schemas/NestedObject"}
                    },
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
    assert (
        result["topLevel"]["properties"]["nested"]["description"] == "A nested string"
    )


def test_dereference_ref_in_list():
    """Test dereferencing a reference within a list."""
    schema = {
        "components": {
            "schemas": {"SimpleString": {"type": "string", "example": "hello"}}
        }
    }
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
