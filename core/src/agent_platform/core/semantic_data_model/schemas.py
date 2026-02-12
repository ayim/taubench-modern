"""Schema types for semantic data models.

This module defines schema-related types for semantic data models,
including validation rules, translations, and the main Schema class.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

# Type alias for JSON data (object or array)
JsonData = dict[str, Any] | list[Any]


def normalize_schema_name(name: str) -> str:
    """Normalize a schema name for uniqueness comparison.

    Normalizes by:
    - Converting to lowercase
    - Replacing spaces with underscores
    - Removing any characters that are not alphanumeric or underscores

    Args:
        name: The schema name to normalize.

    Returns:
        The normalized schema name.
    """
    import re

    # Lowercase
    normalized = name.lower()
    # Replace spaces with underscores
    normalized = normalized.replace(" ", "_")
    # Remove any characters that are not alphanumeric or underscores
    normalized = re.sub(r"[^a-z0-9_]", "", normalized)
    return normalized


class Validation(BaseModel):
    """A validation rule for the values of an object created by a Schema.

    A Schema asserts that some JSON adheres to some given structure. A Validation
    applies a more "semantic" validation that the object is sane.

    For example: a 'name' field is a non-empty string. A sum over a list of
    numbers is equal to a 'total' field.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(
        ...,
        min_length=1,
        description="A unique name for this validation rule within a schema.",
    )
    description: str = Field(
        ...,
        min_length=1,
        description="A description of what this validation rule checks.",
    )
    jq_expression: str = Field(
        ...,
        min_length=1,
        description="A JQ expression that evaluates to true if the data is valid.",
    )


class Transformation(BaseModel):
    """A set of rules that converts an object of one Schema to another Schema.

    A Transformationf expresses computation that transforms data from one Schema
    to another Schema. This logic verifies that resulting data adheres to the
    target Schema.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    target_schema_name: str = Field(
        ...,
        min_length=1,
        description="The name of the target schema to which data will be translated.",
    )

    jq_expression: str = Field(
        ...,
        min_length=1,
        description="A JQ expression that transforms data to conform to the target schema.",
    )


class DocumentExtraction(BaseModel):
    """Configuration for extracting data from documents into a Schema's shape.

    When present on a Schema, indicates the schema can be populated via
    document extraction. The Schema defines "what shape" - these hints
    describe "how to get it" from documents.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    system_prompt: str = Field(
        default="",
        description="Optional system prompt to guide the extraction model.",
    )
    configuration: dict[str, Any] = Field(
        default_factory=dict,
        description="Opaque configuration dict for the extraction engine.",
    )


class Schema(BaseModel):
    """A schema defines the structure and validation rules for data.

    Schemas use JSON Schema format to define the expected structure of data,
    along with optional validation rules and translations for internationalization.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    name: str = Field(
        ...,
        min_length=1,
        description="A unique name for this schema. Must be unique across all schemas in all SDMs.",
    )

    description: str = Field(
        ...,
        min_length=1,
        description="A description of what this schema validates and its purpose.",
    )

    json_schema: dict[str, Any] = Field(
        ...,
        description="A valid JSON Schema that defines the structure of data to validate.",
    )

    validations: list[Validation] = Field(
        default_factory=list,
        description="Custom validation rules to apply beyond JSON Schema validation.",
    )

    transformations: list[Transformation] = Field(
        default_factory=list,
        description="Rules to convert JSON data to another Schema.",
    )

    document_extraction: DocumentExtraction | None = Field(
        default=None,
        description="If present, this schema can be populated via document extraction.",
    )

    @field_validator("name", "description", mode="before")
    @classmethod
    def strip_string_fields(cls, v: str) -> str:
        """Strip whitespace from string fields."""
        return v.strip()

    @field_validator("name", mode="after")
    @classmethod
    def validate_name_not_empty(cls, v: str) -> str:
        """Validate that name is not empty after stripping."""
        if not v:
            raise ValueError("Schema name cannot be empty")
        return v

    @field_validator("description", mode="after")
    @classmethod
    def validate_description_not_empty(cls, v: str) -> str:
        """Validate that description is not empty after stripping."""
        if not v:
            raise ValueError("Schema description cannot be empty")
        return v

    @field_validator("validations", "transformations", mode="before")
    @classmethod
    def ensure_list_type(cls, v: Any, info: ValidationInfo) -> list:
        """Ensure validations and transformations are lists, not None or other types."""
        if v is None:
            return []
        if not isinstance(v, list):
            raise ValueError(f"{info.field_name} must be a list, got {type(v).__name__}")
        return v

    @field_validator("json_schema", mode="after")
    @classmethod
    def validate_json_schema(cls, v: dict[str, Any]) -> dict[str, Any]:
        """Validate that the provided json_schema adheres to our custom JsonSchema definition"""
        from agent_platform.core.semantic_data_model.jsonschema import CustomDraft202012Validator

        # Raises SchemaError when invalid
        CustomDraft202012Validator.check_schema(v)

        return v

    @field_validator("validations", mode="after")
    @classmethod
    def validate_unique_validation_names(cls, v: list[Validation]) -> list[Validation]:
        """Validate that all validations have unique names within this schema."""
        names = [validation.name for validation in v]
        if len(names) != len(set(names)):
            seen: set[str] = set()
            duplicates: list[str] = []
            for name in names:
                if name in seen:
                    duplicates.append(name)
                seen.add(name)
            raise ValueError(f"Validation names must be unique within a schema. Duplicates: {duplicates}")
        return v

    @field_validator("transformations", mode="after")
    @classmethod
    def validate_unique_transformation_targets(cls, v: list[Transformation]) -> list[Transformation]:
        """Validate that all transformations have unique target_schema_name within this schema."""
        targets = [t.target_schema_name for t in v]
        if len(targets) != len(set(targets)):
            seen: set[str] = set()
            duplicates: list[str] = []
            for target in targets:
                if target in seen:
                    duplicates.append(target)
                seen.add(target)
            raise ValueError(
                f"Transformation target_schema_name must be unique within a schema. Duplicates: {duplicates}"
            )
        return v


class ValidationResult(BaseModel):
    """Result of executing a single validation rule against data."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    validation: Validation = Field(
        ...,
        description="The full Validation object that was applied.",
    )
    passed: bool = Field(
        ...,
        description="Whether the validation passed.",
    )
    message: str = Field(
        ...,
        description="Describes the validation outcome.",
    )


class ValidationEvent(BaseModel):
    """Records a validation against a schema in the lineage history."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_: Schema = Field(
        ...,
        alias="schema",
        description="The full Schema used for validation.",
    )
    results: list[ValidationResult] = Field(
        ...,
        description="Results of each validation rule.",
    )
    timestamp: datetime = Field(
        ...,
        description="When the validation occurred.",
    )

    @property
    def is_valid(self) -> bool:
        """Return True if all validation results passed."""
        return all(result.passed for result in self.results)

    def __str__(self) -> str:
        """Return a human-readable representation of the validation event."""
        status = "PASSED" if self.is_valid else "FAILED"
        passed_count = sum(1 for r in self.results if r.passed)
        total_count = len(self.results)
        return (
            f"ValidationEvent({status}): Schema '{self.schema_.name}' at {self.timestamp.isoformat()} "
            f"- {passed_count}/{total_count} validations passed"
        )


class TransformationEvent(BaseModel):
    """Records a transformation between schemas in the lineage history."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_schema: Schema = Field(
        ...,
        description="The full source Schema.",
    )
    target_schema: Schema = Field(
        ...,
        description="The full target Schema.",
    )
    timestamp: datetime = Field(
        ...,
        description="When the translation occurred.",
    )
    conforms_to_target: bool = Field(
        ...,
        description="Whether the translated data matches the shape of the target schema.",
    )
    message: str = Field(
        ...,
        description="Explains why the data doesn't match (or success message).",
    )

    @property
    def is_valid(self) -> bool:
        """Return True if the translation conforms to the target schema."""
        return self.conforms_to_target

    def __str__(self) -> str:
        """Return a human-readable representation of the transformation event."""
        status = "SUCCESS" if self.conforms_to_target else "FAILED"
        return (
            f"TransformationEvent({status}): '{self.source_schema.name}' -> '{self.target_schema.name}' "
            f"at {self.timestamp.isoformat()} - {self.message}"
        )


class ExtractionEvent(BaseModel):
    """Records a document extraction in the lineage history."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_: Schema = Field(
        ...,
        alias="schema",
        description="The Schema used for extraction.",
    )
    timestamp: datetime = Field(
        ...,
        description="When the extraction occurred.",
    )
    success: bool = Field(
        ...,
        description="Whether the extraction succeeded.",
    )
    message: str = Field(
        ...,
        description="Describes the extraction outcome.",
    )

    @property
    def is_valid(self) -> bool:
        """Return True if the extraction was successful."""
        return self.success

    def __str__(self) -> str:
        """Return a human-readable representation of the extraction event."""
        status = "SUCCESS" if self.success else "FAILED"
        return (
            f"ExtractionEvent({status}): Schema '{self.schema_.name}' at {self.timestamp.isoformat()} - {self.message}"
        )


# Union type for lineage events
LineageEvent = ValidationEvent | TransformationEvent | ExtractionEvent


class SchemaData(BaseModel):
    """Wrapper that carries JSON data alongside its lineage metadata.

    The lineage is NOT stored in the user's data - it's separate metadata.
    """

    model_config = ConfigDict(extra="forbid")

    data: JsonData = Field(
        ...,
        description="The actual user data (object or array).",
    )
    history: list[LineageEvent] = Field(
        default_factory=list,
        description="All events (validations and translations) in order.",
    )
    current_schema: Schema | None = Field(
        default=None,
        description="Schema this data currently conforms to.",
    )

    @property
    def is_valid(self) -> bool:
        """Determine if the last lineage event indicates a successful operation.

        Returns True if:
        - History is empty (no operations have failed)
        - Last event's is_valid property returns True

        Returns False if:
        - Last event's is_valid property returns False
        """
        if not self.history:
            return True

        return self.history[-1].is_valid
