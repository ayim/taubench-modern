"""Tests for CustomDraft202012Validator with example JSON schemas."""

import pytest

from agent_platform.core.semantic_data_model.jsonschema import (
    CustomDraft202012Validator,
    SchemaAnnotationError,
)


def test_standard_jsonschema_validates():
    """Standard JSON Schema without custom annotations should validate."""
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer", "minimum": 0},
            "email": {"type": "string", "format": "email"},
        },
        "required": ["name", "email"],
    }
    CustomDraft202012Validator.check_schema(schema)


def test_schema_with_valid_synonyms_and_sample_values():
    """Schema with valid custom annotations should validate."""
    schema = {
        "type": "object",
        "properties": {
            "customer_name": {
                "type": "string",
                "synonyms": ["client_name", "buyer_name", "purchaser"],
                "sample_values": ["John Doe", "Jane Smith"],
            },
            "order_total": {
                "type": "number",
                "minimum": 0,
                "synonyms": ["total", "amount"],
                "sample_values": [99.99, 150.00, 0],
            },
        },
    }
    CustomDraft202012Validator.check_schema(schema)


def test_synonyms_as_string_raises_error():
    """Synonyms as a string instead of list should raise SchemaAnnotationError."""
    schema = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "synonyms": "alternate_name",
            },
        },
    }
    with pytest.raises(SchemaAnnotationError):
        CustomDraft202012Validator.check_schema(schema)


def test_synonyms_with_non_string_elements_raises_error():
    """Synonyms list containing non-strings should raise SchemaAnnotationError."""
    schema = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "synonyms": ["valid_name", 123, None],
            },
        },
    }
    with pytest.raises(SchemaAnnotationError):
        CustomDraft202012Validator.check_schema(schema)


def test_synonyms_on_object_property():
    """Synonyms on an object-typed property should validate."""
    schema = {
        "type": "object",
        "properties": {
            "billing_address": {
                "type": "object",
                "synonyms": ["invoice_address", "payment_address"],
                "properties": {
                    "street": {"type": "string"},
                    "city": {"type": "string"},
                },
            },
        },
    }
    CustomDraft202012Validator.check_schema(schema)


def test_sample_values_valid_strings():
    """Sample values matching string type should validate."""
    schema = {
        "type": "object",
        "properties": {
            "color": {
                "type": "string",
                "sample_values": ["red", "green", "blue"],
            },
        },
    }
    CustomDraft202012Validator.check_schema(schema)


def test_sample_values_invalid_type_for_string_raises_error():
    """Sample values with wrong type for string schema should raise SchemaAnnotationError."""
    schema = {
        "type": "object",
        "properties": {
            "color": {
                "type": "string",
                "sample_values": [123, 456],
            },
        },
    }
    with pytest.raises(SchemaAnnotationError):
        CustomDraft202012Validator.check_schema(schema)


def test_sample_values_valid_integers():
    """Sample values matching integer type should validate."""
    schema = {
        "type": "object",
        "properties": {
            "quantity": {
                "type": "integer",
                "minimum": 0,
                "sample_values": [1, 5, 100],
            },
        },
    }
    CustomDraft202012Validator.check_schema(schema)


def test_sample_values_violating_minimum_constraint_raises_error():
    """Sample values violating minimum constraint should raise SchemaAnnotationError."""
    schema = {
        "type": "object",
        "properties": {
            "quantity": {
                "type": "integer",
                "minimum": 0,
                "sample_values": [-1, -5],
            },
        },
    }
    with pytest.raises(SchemaAnnotationError):
        CustomDraft202012Validator.check_schema(schema)


def test_sample_values_not_allowed_on_object_type():
    """Sample values on object types should raise SchemaAnnotationError."""
    schema = {
        "type": "object",
        "properties": {
            "address": {
                "type": "object",
                "properties": {
                    "street": {"type": "string"},
                    "city": {"type": "string"},
                },
                "sample_values": [
                    {"street": "123 Main St", "city": "Boston"},
                ],
            },
        },
    }
    with pytest.raises(SchemaAnnotationError):
        CustomDraft202012Validator.check_schema(schema)


def test_sample_values_valid_array():
    """Sample values matching array schema should validate."""
    schema = {
        "type": "object",
        "properties": {
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "sample_values": [
                    ["red", "green", "blue"],
                    ["small", "medium", "large"],
                ],
            },
        },
    }
    CustomDraft202012Validator.check_schema(schema)


def test_sample_values_invalid_array_items_raises_error():
    """Sample values with wrong array item types should raise SchemaAnnotationError."""
    schema = {
        "type": "object",
        "properties": {
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "sample_values": [
                    [1, 2, 3],  # integers instead of strings
                ],
            },
        },
    }
    with pytest.raises(SchemaAnnotationError):
        CustomDraft202012Validator.check_schema(schema)
