import json

import pytest

from sema4ai_docint.agent_server_client.client import AgentServerClient


class TestSanitizeJsonSchema:
    """Test cases for JsonSchemaSanitizer class using JSON-based assertions."""

    def assert_json_equal(self, actual, expected):
        """Helper method to compare JSON objects with detailed error messages."""
        if actual != expected:
            pytest.fail(
                f"JSON mismatch:\nActual: {json.dumps(actual, indent=2)}\n"
                f"Expected: {json.dumps(expected, indent=2)}"
            )

    def test_non_array_types_should_remain_unchanged(self):
        """Test that non-array types are left unchanged."""
        test_case = {
            "input": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "number"},
                    "active": {"type": "boolean"},
                },
            },
            "expected": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "number"},
                    "active": {"type": "boolean"},
                },
            },
        }

        result = AgentServerClient.sanitize_json_schema(test_case["input"])
        self.assert_json_equal(result, test_case["expected"])

    def test_remove_null_from_type_array(self):
        """Test that type array with 2 elements including null removes null."""
        test_case = {
            "input": {
                "type": "object",
                "properties": {
                    "intermediaryBank": {
                        "type": ["string", "null"],
                        "const": "JP Morgan Chase Bank",
                    },
                    "amount": {"type": ["number", "null"]},
                    "isActive": {"type": ["null", "boolean"]},
                    "is_minor": {"type": "boolean"},
                },
            },
            "expected": {
                "type": "object",
                "properties": {
                    "intermediaryBank": {
                        "type": "string",
                        "const": "JP Morgan Chase Bank",
                    },
                    "amount": {"type": "number"},
                    "isActive": {"type": "boolean"},
                    "is_minor": {"type": "boolean"},
                },
            },
        }

        result = AgentServerClient.sanitize_json_schema(test_case["input"])
        self.assert_json_equal(result, test_case["expected"])

    def test_single_element_array_converts_to_non_array(self):
        """Test that type array with single element is converted to non-array."""
        test_case = {
            "input": {
                "type": "object",
                "properties": {
                    "singleString": {"type": ["string"]},
                    "singleNumber": {"type": ["number"]},
                    "singleBoolean": {"type": ["boolean"]},
                },
            },
            "expected": {
                "type": "object",
                "properties": {
                    "singleString": {"type": "string"},
                    "singleNumber": {"type": "number"},
                    "singleBoolean": {"type": "boolean"},
                },
            },
        }

        result = AgentServerClient.sanitize_json_schema(test_case["input"])
        self.assert_json_equal(result, test_case["expected"])

    def test_nested_objects_should_be_sanitized_recursively(self):
        """Test that nested objects are sanitized recursively."""
        test_case = {
            "input": {
                "type": "object",
                "properties": {
                    "user": {
                        "type": "object",
                        "properties": {
                            "name": {"type": ["string", "null"]},
                            "profile": {
                                "type": "object",
                                "properties": {
                                    "email": {"type": ["string", "null"]},
                                    "age": {"type": ["number", "null"]},
                                },
                            },
                        },
                    }
                },
            },
            "expected": {
                "type": "object",
                "properties": {
                    "user": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "profile": {
                                "type": "object",
                                "properties": {
                                    "email": {"type": "string"},
                                    "age": {"type": "number"},
                                },
                            },
                        },
                    }
                },
            },
        }

        result = AgentServerClient.sanitize_json_schema(test_case["input"])
        self.assert_json_equal(result, test_case["expected"])

    def test_array_items_should_be_sanitized(self):
        """Test that array items schemas are sanitized."""
        test_case = {
            "input": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": ["string", "null"]},
                                "value": {"type": ["number", "null"]},
                            },
                        },
                    }
                },
            },
            "expected": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "value": {"type": "number"},
                            },
                        },
                    }
                },
            },
        }

        result = AgentServerClient.sanitize_json_schema(test_case["input"])
        self.assert_json_equal(result, test_case["expected"])

    def test_complex_nested_structure_should_be_sanitized(self):
        """Test sanitization of complex nested structures."""
        test_case = {
            "input": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": ["string", "null"]},
                                "metadata": {
                                    "type": "object",
                                    "properties": {
                                        "tags": {
                                            "type": "array",
                                            "items": {"type": ["string", "null"]},
                                        }
                                    },
                                },
                            },
                        },
                    }
                },
            },
            "expected": {
                "type": "object",
                "properties": {
                    "data": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string"},
                                "metadata": {
                                    "type": "object",
                                    "properties": {
                                        "tags": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                        }
                                    },
                                },
                            },
                        },
                    }
                },
            },
        }

        result = AgentServerClient.sanitize_json_schema(test_case["input"])
        self.assert_json_equal(result, test_case["expected"])

    def test_sanitize_empty_schema(self):
        """Test sanitization of empty schema."""
        test_case = {"input": {}, "expected": {}}

        result = AgentServerClient.sanitize_json_schema(test_case["input"])
        self.assert_json_equal(result, test_case["expected"])

    def test_other_properties_should_be_preserved(self):
        """Test that other properties are preserved during sanitization."""
        test_case = {
            "input": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": ["string", "null"],
                        "description": "User name",
                        "maxLength": 100,
                        "pattern": "^[a-zA-Z]+$",
                    }
                },
            },
            "expected": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "User name",
                        "maxLength": 100,
                        "pattern": "^[a-zA-Z]+$",
                    }
                },
            },
        }

        result = AgentServerClient.sanitize_json_schema(test_case["input"])
        self.assert_json_equal(result, test_case["expected"])

    def test_all_supported_types_with_null_should_be_sanitized(self):
        """Test sanitization with all supported JSON Schema types."""
        test_case = {
            "input": {
                "type": "object",
                "properties": {
                    "stringField": {"type": ["string", "null"]},
                    "numberField": {"type": ["number", "null"]},
                    "integerField": {"type": ["integer", "null"]},
                    "booleanField": {"type": ["boolean", "null"]},
                    "arrayField": {"type": ["array", "null"]},
                    "objectField": {"type": ["object", "null"]},
                    "nullFirst": {"type": ["null", "string"]},
                },
            },
            "expected": {
                "type": "object",
                "properties": {
                    "stringField": {"type": "string"},
                    "numberField": {"type": "number"},
                    "integerField": {"type": "integer"},
                    "booleanField": {"type": "boolean"},
                    "arrayField": {"type": "array"},
                    "objectField": {"type": "object"},
                    "nullFirst": {"type": "string"},
                },
            },
        }

        result = AgentServerClient.sanitize_json_schema(test_case["input"])
        self.assert_json_equal(result, test_case["expected"])

    def test_sanitization_should_not_mutate_original_schema(self):
        """Test that sanitization doesn't mutate the original schema."""
        original_input = {
            "type": "object",
            "properties": {"name": {"type": ["string", "null"]}},
        }
        expected_output = {"type": "object", "properties": {"name": {"type": "string"}}}

        # Make a deep copy to verify original is unchanged
        import copy

        original_copy = copy.deepcopy(original_input)

        result = AgentServerClient.sanitize_json_schema(original_input)

        # Original should be unchanged
        self.assert_json_equal(original_input, original_copy)
        # Result should be different
        self.assert_json_equal(result, expected_output)

    # Error case tests
    def test_array_with_more_than_two_elements_should_raise_error(self):
        """Test that array with more than 2 elements raises ValueError."""
        test_case = {
            "input": {
                "type": "object",
                "properties": {"multiType": {"type": ["string", "number", "boolean"]}},
            }
        }

        with pytest.raises(ValueError, match="type should be a string, but was a list"):
            AgentServerClient.sanitize_json_schema(test_case["input"])

    def test_sanitize_array_with_two_non_null_elements_fails(self):
        """Test that array with 2 elements but neither is null raises ValueError."""
        test_case = {
            "input": {
                "type": "object",
                "properties": {"invalidType": {"type": ["string", "number"]}},
            }
        }

        with pytest.raises(ValueError, match="type should be a string, but was a list"):
            AgentServerClient.sanitize_json_schema(test_case["input"])

    def test_empty_array_should_raise_error(self):
        """Test that empty array raises ValueError."""
        test_case = {"input": {"type": "object", "properties": {"emptyType": {"type": []}}}}

        with pytest.raises(ValueError, match="type should be a string, but was a list"):
            AgentServerClient.sanitize_json_schema(test_case["input"])

    def test_nested_error_propagation(self):
        """Test that errors in nested objects are properly propagated."""
        test_case = {
            "input": {
                "type": "object",
                "properties": {
                    "user": {
                        "type": "object",
                        "properties": {"invalidField": {"type": ["string", "number", "boolean"]}},
                    }
                },
            }
        }

        with pytest.raises(ValueError, match="type should be a string, but was a list"):
            AgentServerClient.sanitize_json_schema(test_case["input"])

    def test_mixed_valid_and_invalid_should_fail_on_first_invalid(self):
        """Test that mixed valid and invalid properties fail on the first invalid one
        encountered."""
        test_case = {
            "input": {
                "type": "object",
                "properties": {
                    "validField": {"type": ["string", "null"]},
                    "invalidField": {"type": ["string", "number", "boolean"]},
                    "anotherValidField": {"type": ["number", "null"]},
                },
            }
        }

        with pytest.raises(ValueError, match="type should be a string, but was a list"):
            AgentServerClient.sanitize_json_schema(test_case["input"])
