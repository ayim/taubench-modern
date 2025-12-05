from sema4ai_docint.utils import _filter_jsonschema, _replace_jsonschema_values


def test_filter_jsonschema():
    """Test that filter_jsonschema can filter out arbitrary data from a jsonschema."""
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "number"},
            "extras": {"type": "string"},
            "address": {
                "type": "object",
                "properties": {
                    "street": {"type": "string"},
                    "city": {"type": "string"},
                    "extras": {"type": "string"},
                },
            },
        },
    }

    # A lambda never says we should remove keys is equal to the original schema (no-op)
    assert schema == _filter_jsonschema(schema, lambda k: False)

    # Remove the "age" key
    ageless = _filter_jsonschema(schema, lambda k: k == "age")
    assert ageless == {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "extras": {"type": "string"},
            "address": {
                "type": "object",
                "properties": {
                    "street": {"type": "string"},
                    "city": {"type": "string"},
                    "extras": {"type": "string"},
                },
            },
        },
    }

    # Don't fail on unknown keys like "type"
    typeless = _filter_jsonschema(schema, lambda k: k == "type")
    assert typeless == {
        "properties": {
            "name": {},
            "age": {},
            "extras": {},
            "address": {
                "properties": {
                    "street": {},
                    "city": {},
                    "extras": {},
                },
            },
        },
    }

    # Remove multiple instances of the "extras" key at arbitrary levels
    no_extras = _filter_jsonschema(schema, lambda k: k == "extras")
    assert no_extras == {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "number"},
            "address": {
                "type": "object",
                "properties": {
                    "street": {"type": "string"},
                    "city": {"type": "string"},
                },
            },
        },
    }


def test_replace_jsonschema_values():
    """Test that replace_jsonschema_values can replace values in a jsonschema."""
    schema = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "metadata": "some details",
                "metadata2": "some other details",
            },
            "age": {
                "type": "number",
                "metadata": "some age details",
                "metadata2": "some other age details",
            },
            "metadata": "object details",
        },
    }

    # Replace the value for metadata with the value from metadata2
    # at the same level
    replacements = {
        "metadata": "metadata2",
    }

    replaced = _replace_jsonschema_values(schema, replacements)
    assert replaced == {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                # replaced with the value from metadata2 inside the name object
                "metadata": "some other details",
                "metadata2": "some other details",
            },
            "age": {
                "type": "number",
                # replaced with the value from metadata2 inside the age object
                "metadata": "some other age details",
                "metadata2": "some other age details",
            },
            # No metadata2 key at this level, so it's left as-is.
            "metadata": "object details",
        },
    }
