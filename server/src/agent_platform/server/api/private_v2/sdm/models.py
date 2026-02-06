from dataclasses import dataclass, field
from typing import Any


@dataclass
class SchemaValidationError:
    """Individual schema validation error."""

    path: str = field(metadata={"description": "The JSON path where the error occurred."})
    message: str = field(metadata={"description": "A descriptive message about the validation error."})


@dataclass
class ValidateJsonSchemaPayload:
    """Payload for validating a JSON schema."""

    json_schema: dict[str, Any] = field(metadata={"description": "The JSON schema to be validated."})


@dataclass
class ValidateJsonSchemaResponse:
    """Response from JSON schema validation."""

    is_valid: bool = field(metadata={"description": "Indicates whether the JSON schema is valid."})
    errors: list[SchemaValidationError] = field(
        default_factory=list, metadata={"description": "List of validation errors if the schema is invalid."}
    )
