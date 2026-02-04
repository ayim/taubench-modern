"""Unit tests for Schema Pydantic model and related classes."""

from datetime import datetime

import pytest

from agent_platform.core.semantic_data_model.schemas import (
    Schema,
    SchemaData,
    Transformation,
    TransformationEvent,
    Validation,
    ValidationEvent,
    ValidationResult,
)


class TestValidation:
    """Tests for Validation stub class."""

    def test_validation_forbids_extra_fields(self):
        """Test that Validation forbids extra fields."""
        with pytest.raises(ValueError, match="Extra inputs are not permitted"):
            Validation(unknown_field="value")  # type: ignore


class TestTransformation:
    """Tests for Transformation stub class."""

    def test_transformation_forbids_extra_fields(self):
        """Test that Transformation forbids extra fields."""
        with pytest.raises(ValueError, match="Extra inputs are not permitted"):
            Transformation(unknown_field="value")  # type: ignore


class TestSchema:
    """Tests for Schema Pydantic model."""

    def test_schema_creation_minimal(self):
        """Test creating a schema with minimal required fields."""
        schema = Schema(
            name="test_schema",
            description="A test schema",
            json_schema={"type": "object", "properties": {}},
        )
        assert schema.name == "test_schema"
        assert schema.description == "A test schema"
        assert schema.json_schema == {"type": "object", "properties": {}}
        assert schema.validations == []
        assert schema.transformations == []

    def test_schema_creation_with_all_fields(self):
        """Test creating a schema with all fields populated."""
        schema = Schema(
            name="full_schema",
            description="A complete schema",
            json_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "required": ["name"],
            },
            validations=[],
            transformations=[],
        )
        assert schema.name == "full_schema"
        assert len(schema.json_schema["properties"]) == 2

    def test_schema_name_stripped(self):
        """Test that schema name is stripped of whitespace."""
        schema = Schema(
            name="  test_schema  ",
            description="Test",
            json_schema={"type": "object", "properties": {}},
        )
        assert schema.name == "test_schema"

    def test_schema_name_empty_raises_error(self):
        """Test that empty name raises validation error."""
        with pytest.raises(ValueError, match="at least 1 character"):
            Schema(
                name="",
                description="Test",
                json_schema={"type": "object", "properties": {}},
            )

    def test_schema_name_whitespace_only_raises_error(self):
        """Test that whitespace-only name raises validation error."""
        with pytest.raises(ValueError, match="at least 1 character"):
            Schema(
                name="   ",
                description="Test",
                json_schema={"type": "object", "properties": {}},
            )

    def test_schema_description_stripped(self):
        """Test that schema description is stripped of whitespace."""
        schema = Schema(
            name="test",
            description="  A description  ",
            json_schema={"type": "object", "properties": {}},
        )
        assert schema.description == "A description"

    def test_schema_description_empty_raises_error(self):
        """Test that empty description raises validation error."""
        with pytest.raises(ValueError, match="at least 1 character"):
            Schema(
                name="test",
                description="",
                json_schema={"type": "object", "properties": {}},
            )

    def test_schema_description_whitespace_only_raises_error(self):
        """Test that whitespace-only description raises validation error."""
        with pytest.raises(ValueError, match="at least 1 character"):
            Schema(
                name="test",
                description="   ",
                json_schema={"type": "object", "properties": {}},
            )

    def test_schema_valid_json_schema(self):
        """Test that a valid JSON Schema passes validation."""
        schema = Schema(
            name="test",
            description="Test",
            json_schema={
                "type": "object",
                "properties": {
                    "email": {"type": "string", "format": "email"},
                },
            },
        )
        assert "properties" in schema.json_schema

    def test_schema_invalid_json_schema_type_raises_error(self):
        """Test that an invalid JSON Schema raises validation error."""
        from jsonschema.exceptions import SchemaError

        with pytest.raises(SchemaError):
            Schema(
                name="test",
                description="Test",
                json_schema={
                    "type": "invalid_type",
                },
            )

    def test_schema_json_schema_with_invalid_property_type(self):
        """Test that JSON Schema with invalid property type raises error."""
        from jsonschema.exceptions import SchemaError

        with pytest.raises(SchemaError):
            Schema(
                name="test",
                description="Test",
                json_schema={
                    "type": "object",
                    "properties": {
                        "field": {"type": "not_a_type"},
                    },
                },
            )

    def test_schema_complex_valid_json_schema(self):
        """Test that a complex valid JSON Schema passes validation."""
        schema = Schema(
            name="complex_schema",
            description="A complex schema",
            json_schema={
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": "object",
                "properties": {
                    "name": {"type": "string", "minLength": 1},
                    "age": {"type": "integer", "minimum": 0},
                    "email": {"type": "string", "format": "email"},
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["name", "email"],
                "additionalProperties": False,
            },
        )
        assert schema.json_schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"

    def test_schema_validation_rules_defaults_to_empty_list(self):
        """Test that validation_rules defaults to empty list."""
        schema = Schema(
            name="test",
            description="Test",
            json_schema={"type": "object", "properties": {}},
        )
        assert schema.validations == []
        assert isinstance(schema.validations, list)

    def test_schema_validation_rules_none_becomes_empty_list(self):
        """Test that None for validation_rules becomes empty list."""
        schema = Schema(
            name="test",
            description="Test",
            json_schema={"type": "object", "properties": {}},
            validations=None,  # type: ignore
        )
        assert schema.validations == []

    def test_schema_validation_rules_non_list_raises_error(self):
        """Test that non-list validation_rules raises error."""
        with pytest.raises(ValueError, match="validations must be a list"):
            Schema(
                name="test",
                description="Test",
                json_schema={"type": "object", "properties": {}},
                validations="not a list",  # type: ignore
            )

    def test_schema_transformations_defaults_to_empty_list(self):
        """Test that Transformations defaults to empty list."""
        schema = Schema(
            name="test",
            description="Test",
            json_schema={"type": "object", "properties": {}},
        )
        assert schema.transformations == []

    def test_schema_transformations_none_becomes_empty_list(self):
        """Test that None for Transformations becomes empty list."""
        schema = Schema(
            name="test",
            description="Test",
            json_schema={"type": "object", "properties": {}},
            transformations=None,  # type: ignore
        )
        assert schema.transformations == []

    def test_schema_transformations_non_list_raises_error(self):
        """Test that non-list Transformations raises error."""
        with pytest.raises(ValueError, match="transformations must be a list"):
            Schema(
                name="test",
                description="Test",
                json_schema={"type": "object", "properties": {}},
                transformations="not a list",  # type: ignore
            )

    def test_schema_duplicate_validation_names_raises_error(self):
        """Test that duplicate validation names within a schema raises error."""
        with pytest.raises(ValueError, match="Validation names must be unique"):
            Schema(
                name="test",
                description="Test",
                json_schema={"type": "object", "properties": {}},
                validations=[
                    Validation(name="check_positive", description="First check", jq_expression=".a > 0"),
                    Validation(name="check_positive", description="Second check", jq_expression=".b > 0"),
                ],
            )

    def test_schema_duplicate_transformation_targets_raises_error(self):
        """Test that duplicate transformation target_schema_name within a schema raises error."""
        with pytest.raises(ValueError, match="Transformation target_schema_name must be unique"):
            Schema(
                name="test",
                description="Test",
                json_schema={"type": "object", "properties": {}},
                transformations=[
                    Transformation(target_schema_name="target_a", jq_expression="."),
                    Transformation(target_schema_name="target_a", jq_expression=". | {x: .y}"),
                ],
            )

    def test_schema_model_dump(self):
        """Test that model_dump works correctly."""
        schema = Schema(
            name="test",
            description="Test schema",
            json_schema={"type": "object", "properties": {}},
        )
        dumped = schema.model_dump()
        assert dumped["name"] == "test"
        assert dumped["description"] == "Test schema"
        assert dumped["json_schema"] == {"type": "object", "properties": {}}
        assert dumped["validations"] == []
        assert dumped["transformations"] == []

    def test_schema_model_validate_from_dict(self):
        """Test that model_validate works from dict."""
        data = {
            "name": "test",
            "description": "Test",
            "json_schema": {"type": "object", "properties": {}},
        }
        schema = Schema.model_validate(data)
        assert schema.name == "test"


class TestSemanticDataModelWithSchemas:
    """Tests for SemanticDataModel with schemas field."""

    def test_sdm_with_schemas(self):
        """Test creating SDM with schemas field."""
        from agent_platform.core.semantic_data_model import Schema, SemanticDataModel

        sdm = SemanticDataModel.model_validate(
            {
                "name": "test_model",
                "tables": [],
                "schemas": [
                    {
                        "name": "user_schema",
                        "description": "Schema for user data",
                        "json_schema": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "email": {"type": "string"},
                            },
                        },
                    }
                ],
            }
        )

        assert sdm.schemas is not None
        assert len(sdm.schemas) == 1
        assert sdm.schemas[0].name == "user_schema"
        assert isinstance(sdm.schemas[0], Schema)

    def test_sdm_with_multiple_schemas(self):
        """Test creating SDM with multiple schemas."""
        from agent_platform.core.semantic_data_model import SemanticDataModel

        sdm = SemanticDataModel.model_validate(
            {
                "name": "test_model",
                "tables": [],
                "schemas": [
                    {
                        "name": "user_schema",
                        "description": "Schema for user data",
                        "json_schema": {"type": "object", "properties": {}},
                    },
                    {
                        "name": "order_schema",
                        "description": "Schema for order data",
                        "json_schema": {"type": "object", "properties": {}},
                    },
                ],
            }
        )

        assert sdm.schemas is not None
        assert len(sdm.schemas) == 2
        assert sdm.schemas[0].name == "user_schema"
        assert sdm.schemas[1].name == "order_schema"

    def test_sdm_without_schemas(self):
        """Test creating SDM without schemas field (backward compatibility)."""
        from agent_platform.core.semantic_data_model import SemanticDataModel

        sdm = SemanticDataModel.model_validate(
            {
                "name": "test_model",
                "tables": [],
            }
        )

        assert sdm.schemas is None

    def test_sdm_model_dump_excludes_none_schemas(self):
        """Test that model_dump excludes None schemas by default."""
        from agent_platform.core.semantic_data_model import SemanticDataModel

        sdm = SemanticDataModel.model_validate(
            {
                "name": "test_model",
                "tables": [],
            }
        )

        dumped = sdm.model_dump()
        assert "schemas" not in dumped

    def test_sdm_model_dump_includes_schemas_when_present(self):
        """Test that model_dump includes schemas when present."""
        from agent_platform.core.semantic_data_model import SemanticDataModel

        sdm = SemanticDataModel.model_validate(
            {
                "name": "test_model",
                "tables": [],
                "schemas": [
                    {
                        "name": "test_schema",
                        "description": "Test",
                        "json_schema": {"type": "object", "properties": {}},
                    }
                ],
            }
        )

        dumped = sdm.model_dump()
        assert "schemas" in dumped
        assert len(dumped["schemas"]) == 1
        assert dumped["schemas"][0]["name"] == "test_schema"

    def test_sdm_roundtrip(self):
        """Test that SDM with schemas survives model_dump/model_validate roundtrip."""
        from agent_platform.core.semantic_data_model import Schema, SemanticDataModel

        original_data = {
            "name": "test_model",
            "tables": [],
            "schemas": [
                {
                    "name": "user_schema",
                    "description": "Schema for user data",
                    "json_schema": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                        },
                    },
                }
            ],
        }

        sdm = SemanticDataModel.model_validate(original_data)
        dumped = sdm.model_dump()
        restored = SemanticDataModel.model_validate(dumped)

        assert restored.schemas is not None
        assert len(restored.schemas) == 1
        assert restored.schemas[0].name == "user_schema"
        assert isinstance(restored.schemas[0], Schema)


class TestSemanticDataModelSchemaUniqueness:
    """Tests for schema name uniqueness within an SDM."""

    def test_sdm_with_unique_schema_names(self):
        """Test that SDM with unique schema names passes validation."""
        from agent_platform.core.semantic_data_model import SemanticDataModel

        sdm = SemanticDataModel.model_validate(
            {
                "name": "test",
                "tables": [],
                "schemas": [
                    {"name": "schema_a", "description": "A", "json_schema": {"type": "object"}},
                    {"name": "schema_b", "description": "B", "json_schema": {"type": "object"}},
                ],
            }
        )
        assert sdm.schemas is not None
        assert len(sdm.schemas) == 2

    def test_sdm_with_normalized_schema_names_raises_error(self):
        """Test that SDM with duplicate schema names raises error."""
        from agent_platform.core.semantic_data_model import SemanticDataModel

        with pytest.raises(ValueError, match="Duplicate schema name"):
            SemanticDataModel.model_validate(
                {
                    "name": "test",
                    "tables": [],
                    "schemas": [
                        # Both should normalize to schema_a
                        {"name": "schema a", "description": "A", "json_schema": {"type": "object"}},
                        {"name": "schema_a", "description": "A", "json_schema": {"type": "object"}},
                    ],
                }
            )

    def test_sdm_with_duplicate_schema_names_raises_error(self):
        """Test that SDM with duplicate schema names raises error."""
        from agent_platform.core.semantic_data_model import SemanticDataModel

        with pytest.raises(ValueError, match="Duplicate schema name"):
            SemanticDataModel.model_validate(
                {
                    "name": "test",
                    "tables": [],
                    "schemas": [
                        {"name": "schema_a", "description": "A", "json_schema": {"type": "object"}},
                        {"name": "schema_a", "description": "B", "json_schema": {"type": "object"}},
                    ],
                }
            )

    def test_sdm_duplicate_schema_names_case_insensitive(self):
        """Test that duplicate detection is case-insensitive."""
        from agent_platform.core.semantic_data_model import SemanticDataModel

        with pytest.raises(ValueError, match="Duplicate schema name"):
            SemanticDataModel.model_validate(
                {
                    "name": "test",
                    "tables": [],
                    "schemas": [
                        {"name": "Schema_A", "description": "A", "json_schema": {"type": "object"}},
                        {"name": "schema_a", "description": "B", "json_schema": {"type": "object"}},
                    ],
                }
            )

    def test_sdm_empty_schemas_list_passes(self):
        """Test that empty schemas list passes validation."""
        from agent_platform.core.semantic_data_model import SemanticDataModel

        sdm = SemanticDataModel.model_validate(
            {
                "name": "test",
                "tables": [],
                "schemas": [],
            }
        )
        assert sdm.schemas == []


class TestValidationEventIsValid:
    """Tests for ValidationEvent.is_valid computed property."""

    @pytest.fixture
    def sample_schema(self) -> Schema:
        """Create a sample schema for tests."""
        return Schema(
            name="test_schema",
            description="A test schema",
            json_schema={"type": "object", "properties": {}},
        )

    @pytest.fixture
    def sample_validation(self) -> Validation:
        """Create a sample validation for tests."""
        return Validation(
            name="test_validation",
            description="A test validation rule",
            jq_expression=".value > 0",
        )

    def test_is_valid_all_passed(self, sample_schema, sample_validation):
        """Test that is_valid returns True when all validation results passed."""
        event = ValidationEvent(
            schema=sample_schema,
            results=[
                ValidationResult(validation=sample_validation, passed=True, message="OK"),
            ],
            timestamp=datetime.now(),
        )
        assert event.is_valid is True

    def test_is_valid_multiple_all_passed(self, sample_schema):
        """Test that is_valid returns True when all validation results passed."""
        validation1 = Validation(name="v1", description="First", jq_expression=".a > 0")
        validation2 = Validation(name="v2", description="Second", jq_expression=".b > 0")
        event = ValidationEvent(
            schema=sample_schema,
            results=[
                ValidationResult(validation=validation1, passed=True, message="OK"),
                ValidationResult(validation=validation2, passed=True, message="OK"),
            ],
            timestamp=datetime.now(),
        )
        assert event.is_valid is True

    def test_is_valid_any_failed(self, sample_schema, sample_validation):
        """Test that is_valid returns False when any validation result failed."""
        event = ValidationEvent(
            schema=sample_schema,
            results=[
                ValidationResult(validation=sample_validation, passed=False, message="Failed"),
            ],
            timestamp=datetime.now(),
        )
        assert event.is_valid is False

    def test_is_valid_mixed_results(self, sample_schema):
        """Test that is_valid returns False when any validation result failed."""
        validation1 = Validation(name="v1", description="First", jq_expression=".a > 0")
        validation2 = Validation(name="v2", description="Second", jq_expression=".b > 0")
        event = ValidationEvent(
            schema=sample_schema,
            results=[
                ValidationResult(validation=validation1, passed=True, message="OK"),
                ValidationResult(validation=validation2, passed=False, message="Failed"),
            ],
            timestamp=datetime.now(),
        )
        assert event.is_valid is False

    def test_is_valid_empty_results(self, sample_schema):
        """Test that is_valid returns True when results list is empty."""
        event = ValidationEvent(
            schema=sample_schema,
            results=[],
            timestamp=datetime.now(),
        )
        assert event.is_valid is True


class TestTransformationEventIsValid:
    """Tests for TransformationEvent.is_valid computed property."""

    @pytest.fixture
    def source_schema(self) -> Schema:
        """Create a source schema for tests."""
        return Schema(
            name="source_schema",
            description="Source schema",
            json_schema={"type": "object", "properties": {}},
        )

    @pytest.fixture
    def target_schema(self) -> Schema:
        """Create a target schema for tests."""
        return Schema(
            name="target_schema",
            description="Target schema",
            json_schema={"type": "object", "properties": {}},
        )

    def test_is_valid_conforms(self, source_schema, target_schema):
        """Test that is_valid returns True when conforms_to_target is True."""
        event = TransformationEvent(
            source_schema=source_schema,
            target_schema=target_schema,
            timestamp=datetime.now(),
            conforms_to_target=True,
            message="Transformation successful",
        )
        assert event.is_valid is True

    def test_is_valid_does_not_conform(self, source_schema, target_schema):
        """Test that is_valid returns False when conforms_to_target is False."""
        event = TransformationEvent(
            source_schema=source_schema,
            target_schema=target_schema,
            timestamp=datetime.now(),
            conforms_to_target=False,
            message="Transformation failed",
        )
        assert event.is_valid is False


class TestSchemaDataIsValid:
    """Tests for SchemaData.is_valid computed property."""

    @pytest.fixture
    def sample_schema(self) -> Schema:
        """Create a sample schema for tests."""
        return Schema(
            name="test_schema",
            description="A test schema",
            json_schema={"type": "object", "properties": {}},
        )

    @pytest.fixture
    def sample_validation(self) -> Validation:
        """Create a sample validation for tests."""
        return Validation(
            name="test_validation",
            description="A test validation rule",
            jq_expression=".value > 0",
        )

    def test_is_valid_empty_history_returns_true(self):
        """Test that is_valid returns True when history is empty."""
        schema_data = SchemaData(data={"key": "value"})
        assert schema_data.is_valid is True

    def test_is_valid_validation_event_all_passed(self, sample_schema, sample_validation):
        """Test that is_valid returns True when all validation results passed."""
        validation_event = ValidationEvent(
            schema=sample_schema,
            results=[
                ValidationResult(
                    validation=sample_validation,
                    passed=True,
                    message="Validation passed",
                ),
            ],
            timestamp=datetime.now(),
        )
        schema_data = SchemaData(data={"key": "value"}, history=[validation_event])
        assert schema_data.is_valid is True

    def test_is_valid_validation_event_multiple_all_passed(self, sample_schema):
        """Test that is_valid returns True when all validation results in event passed."""
        validation1 = Validation(name="validation1", description="First", jq_expression=".a > 0")
        validation2 = Validation(name="validation2", description="Second", jq_expression=".b > 0")
        validation_event = ValidationEvent(
            schema=sample_schema,
            results=[
                ValidationResult(validation=validation1, passed=True, message="OK"),
                ValidationResult(validation=validation2, passed=True, message="OK"),
            ],
            timestamp=datetime.now(),
        )
        schema_data = SchemaData(data={"a": 1, "b": 2}, history=[validation_event])
        assert schema_data.is_valid is True

    def test_is_valid_validation_event_any_failed(self, sample_schema, sample_validation):
        """Test that is_valid returns False when any validation result failed."""
        validation_event = ValidationEvent(
            schema=sample_schema,
            results=[
                ValidationResult(
                    validation=sample_validation,
                    passed=False,
                    message="Validation failed",
                ),
            ],
            timestamp=datetime.now(),
        )
        schema_data = SchemaData(data={"key": "value"}, history=[validation_event])
        assert schema_data.is_valid is False

    def test_is_valid_validation_event_mixed_results(self, sample_schema):
        """Test that is_valid returns False when any validation in event failed."""
        validation1 = Validation(name="validation1", description="First", jq_expression=".a > 0")
        validation2 = Validation(name="validation2", description="Second", jq_expression=".b > 0")
        validation_event = ValidationEvent(
            schema=sample_schema,
            results=[
                ValidationResult(validation=validation1, passed=True, message="OK"),
                ValidationResult(validation=validation2, passed=False, message="Failed"),
            ],
            timestamp=datetime.now(),
        )
        schema_data = SchemaData(data={"a": 1, "b": -1}, history=[validation_event])
        assert schema_data.is_valid is False

    def test_is_valid_transformation_event_conforms(self, sample_schema):
        """Test that is_valid returns True when Transformation conforms to target."""
        target_schema = Schema(
            name="target_schema",
            description="Target schema",
            json_schema={"type": "object", "properties": {}},
        )
        transformation_event = TransformationEvent(
            source_schema=sample_schema,
            target_schema=target_schema,
            timestamp=datetime.now(),
            conforms_to_target=True,
            message="Transformation successful",
        )
        schema_data = SchemaData(data={"key": "value"}, history=[transformation_event])
        assert schema_data.is_valid is True

    def test_is_valid_transformation_event_does_not_conform(self, sample_schema):
        """Test that is_valid returns False when Transformation does not conform."""
        target_schema = Schema(
            name="target_schema",
            description="Target schema",
            json_schema={"type": "object", "properties": {}},
        )
        transformation_event = TransformationEvent(
            source_schema=sample_schema,
            target_schema=target_schema,
            timestamp=datetime.now(),
            conforms_to_target=False,
            message="Transformation failed to conform",
        )
        schema_data = SchemaData(data={"key": "value"}, history=[transformation_event])
        assert schema_data.is_valid is False

    def test_is_valid_checks_only_last_event(self, sample_schema, sample_validation):
        """Test that is_valid only checks the last event in history."""
        # First event: failed validation
        failed_event = ValidationEvent(
            schema=sample_schema,
            results=[
                ValidationResult(
                    validation=sample_validation,
                    passed=False,
                    message="Failed",
                ),
            ],
            timestamp=datetime.now(),
        )
        # Second event: successful validation
        passed_event = ValidationEvent(
            schema=sample_schema,
            results=[
                ValidationResult(
                    validation=sample_validation,
                    passed=True,
                    message="Passed",
                ),
            ],
            timestamp=datetime.now(),
        )
        # Last event is successful, so is_valid should be True
        schema_data = SchemaData(data={"key": "value"}, history=[failed_event, passed_event])
        assert schema_data.is_valid is True

    def test_is_valid_last_event_failed_after_success(self, sample_schema, sample_validation):
        """Test that is_valid returns False when last event failed after prior success."""
        # First event: successful validation
        passed_event = ValidationEvent(
            schema=sample_schema,
            results=[
                ValidationResult(
                    validation=sample_validation,
                    passed=True,
                    message="Passed",
                ),
            ],
            timestamp=datetime.now(),
        )
        # Second event: failed validation
        failed_event = ValidationEvent(
            schema=sample_schema,
            results=[
                ValidationResult(
                    validation=sample_validation,
                    passed=False,
                    message="Failed",
                ),
            ],
            timestamp=datetime.now(),
        )
        # Last event is failed, so is_valid should be False
        schema_data = SchemaData(data={"key": "value"}, history=[passed_event, failed_event])
        assert schema_data.is_valid is False
