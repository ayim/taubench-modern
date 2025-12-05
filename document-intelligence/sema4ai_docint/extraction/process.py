import json
import logging
from typing import Any

from pydantic import BaseModel, field_validator

from sema4ai_docint.models import (
    Mapping,
    MappingRow,
)

logger = logging.getLogger(__name__)

ExtractionSchema = dict[str, Any]  # Dict containing JSONSchema structure for extraction
TranslationSchema = dict[str, Any]  # Dict containing rules array for transformation

# Union types for function parameters
ExtractionSchemaInput = str | ExtractionSchema
TranslationSchemaInput = str | TranslationSchema


class ExtractAndTransformContentParams(BaseModel):
    """Parameters for the extract_and_transform_content function.

    Attributes:
        file_name: PDF file name to process
        extraction_schema: Extraction schema to use for processing (string)
        translation_schema: Translation schema as dict with string keys - MUST contain "rules" key
        data_model_name: Data model name for document
        layout_name: Document layout to use for processing
        start_page: Optional start page for extraction (1-indexed)
        end_page: Optional end page for extraction (1-indexed)
    """

    file_name: str
    extraction_schema: str
    translation_schema: dict[str, Any]  # Must contain "rules" key
    data_model_name: str
    layout_name: str
    start_page: int | None = None
    end_page: int | None = None

    @field_validator("translation_schema")
    @classmethod
    def validate_translation_schema(cls, v):
        """Validate that translation_schema has the correct structure."""
        if not isinstance(v, dict):
            raise ValueError("translation_schema must be a dictionary object")

        if "rules" not in v:
            raise ValueError("translation_schema must contain a 'rules' key")

        if not isinstance(v["rules"], list):
            raise ValueError("translation_schema 'rules' field must be an array")

        if not v["rules"]:
            raise ValueError("translation_schema 'rules' array cannot be empty")

        # Validate each rule has required fields
        for i, rule in enumerate(v["rules"]):
            if not isinstance(rule, dict):
                raise ValueError(f"Rule {i} must be a dictionary object")
            if "source" not in rule or "target" not in rule:
                raise ValueError(f"Rule {i} must contain 'source' and 'target' fields")

        return v

    @field_validator("extraction_schema")
    @classmethod
    def validate_extraction_schema(cls, v):
        """Validate that extraction_schema is a valid JSON string."""
        if not isinstance(v, str):
            raise ValueError("extraction_schema must be a string")

        try:
            json.loads(v)
        except json.JSONDecodeError as e:
            raise ValueError(f"extraction_schema must be valid JSON: {e!s}") from e

        return v

    @field_validator("data_model_name", "layout_name")
    @classmethod
    def validate_names(cls, v):
        """Validate that names are not empty."""
        if not v or not v.strip():
            raise ValueError("data_model_name and layout_name cannot be empty")
        return v.strip()


# TODO: Fix lint issues in this function
def _validate_translation_schema_format(  # noqa: PLR0911
    translation_schema: dict[str, Any],
) -> tuple[bool, str]:
    """Validate translation schema format and return detailed error message if invalid.

    Args:
        translation_schema: The translation schema to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(translation_schema, dict):
        return (
            False,
            "translation_schema must be a dictionary object, not a list or string",
        )

    if "rules" not in translation_schema:
        return (
            False,
            "translation_schema must contain a 'rules' key. Expected format: {'rules': [...]}",
        )

    if not isinstance(translation_schema["rules"], list):
        return (
            False,
            "translation_schema 'rules' field must be an array/list, not a string or object",
        )

    if not translation_schema["rules"]:
        return False, "translation_schema 'rules' array cannot be empty"

    for i, rule in enumerate(translation_schema["rules"]):
        if not isinstance(rule, dict):
            return (
                False,
                f"Rule {i} must be a dictionary object, not a string or other type",
            )
        if "source" not in rule or "target" not in rule:
            return False, f"Rule {i} must contain both 'source' and 'target' fields"

    return True, ""


# TODO: Fix lint issues in this function
def validate_and_parse_schemas(  # noqa: C901, PLR0912
    extraction_schema: str | dict,
    translation_schema: str | dict,
) -> tuple[ExtractionSchema, TranslationSchema]:
    """Validate and parse extraction schema and translation schema.

    Args:
        extraction_schema: Extraction schema (string or dict)
        translation_schema: Translation schema (string or dict)

    Returns:
        Tuple of (parsed_extraction_schema, parsed_translation_schema)

    Raises:
        ValueError: If schemas are invalid
    """
    # Validate extraction schema
    if not extraction_schema:
        raise ValueError("Extraction schema is required")

    # Parse extraction schema if it's a string
    if isinstance(extraction_schema, str):
        try:
            parsed_extraction_schema = json.loads(extraction_schema)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid extraction schema JSON: {e!s}") from e
    else:
        parsed_extraction_schema = extraction_schema

    # Validate that extraction schema is a dict
    if not isinstance(parsed_extraction_schema, dict):
        raise ValueError("Extraction schema must be a valid JSON object")

    # Parse translation rules if it's a string
    if isinstance(translation_schema, str):
        try:
            parsed_translation_schema = json.loads(translation_schema)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid translation rules JSON: {e!s}") from e
    else:
        parsed_translation_schema = translation_schema

    # Validate translation rules
    if not parsed_translation_schema:
        raise ValueError("Translation rules are required")

    # Handle case where translation schema is a list (array) instead of object with "rules" key
    if isinstance(parsed_translation_schema, list):
        # Convert array to expected format with "rules" key
        parsed_translation_schema = {"rules": parsed_translation_schema}
        logger.info("Converted translation schema from list to object with 'rules' key")

    if not isinstance(parsed_translation_schema, dict):
        raise ValueError("Translation rules must be a valid JSON object")

    # Use the helper function for detailed validation
    is_valid, error_msg = _validate_translation_schema_format(parsed_translation_schema)
    if not is_valid:
        raise ValueError(f"Translation schema validation failed: {error_msg}")

    # Validate that the translation schema is a valid Mapping object
    try:
        _ = Mapping(rules=[MappingRow(**rule) for rule in parsed_translation_schema["rules"]])
    except Exception as e:
        raise ValueError(f"Translation schema rules are invalid: {e!s}") from e

    return parsed_extraction_schema, parsed_translation_schema
