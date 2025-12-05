import jsonschema

from sema4ai_docint.utils import validate_extraction_schema


def validate_json_extraction_schema(schema_dict: dict) -> tuple[bool, str]:
    """
    Validate that a dictionary is a valid JSON schema for extraction.

    Args:
        schema_dict: The dictionary to validate as a JSON schema

    Returns:
        tuple[bool, str]: (is_valid, error_message)
    """
    try:
        # Check if it's a valid JSON schema by trying to create a validator
        validate_extraction_schema(schema_dict)
        return True, ""
    except (jsonschema.SchemaError, ValueError) as e:
        return False, f"Invalid JSON schema: {e!s}"
    except Exception as e:
        return False, f"Schema validation error: {e!s}"
