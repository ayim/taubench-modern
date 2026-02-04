"""Unit tests for SchemaService and DocumentService."""

from datetime import datetime

import pytest
import pytz

from agent_platform.core.semantic_data_model.schemas import (
    JsonData,
    Schema,
    SchemaData,
    Transformation,
    TransformationEvent,
    Validation,
    ValidationEvent,
)
from agent_platform.core.semantic_data_model.service import (
    DocumentService,
    SchemaService,
)


class StubSchemaService(SchemaService):
    """Subclass that provides concrete implementations for testing validate()."""

    def __init__(self, validation_results: dict[str, tuple[bool, str]] | None = None):
        self._validation_results = validation_results or {}

    def _execute_validation_rule(self, data: JsonData, rule: Validation) -> tuple[bool, str]:
        return self._validation_results.get(rule.name, (True, "Passed"))


class StubSchemaServiceForTransform(SchemaService):
    """Subclass that provides concrete implementations for testing transform()."""

    def __init__(
        self,
        transform_result: tuple[JsonData | None, str | None] = ({"transformed": True}, None),
        conformance_result: tuple[bool, str] = (True, "Conforms"),
    ):
        self._transform_result = transform_result
        self._conformance_result = conformance_result

    def _execute_transformation(
        self, data: JsonData, transformation: Transformation
    ) -> tuple[JsonData | None, str | None]:
        return self._transform_result

    def _check_schema_conformance(self, data: JsonData, schema: Schema) -> tuple[bool, str]:
        return self._conformance_result


class TestSchemaServiceCreateSchemaData:
    """Tests for SchemaService.create_schema_data()."""

    def test_create_schema_data_with_dict(self):
        """Test creating SchemaData from a dictionary."""
        service = SchemaService()
        data = {"name": "Alice", "age": 30}

        result = service.create_schema_data(data)

        assert result.data == data
        assert result.history == []
        assert result.current_schema is None

    def test_create_schema_data_with_list(self):
        """Test creating SchemaData from a list."""
        service = SchemaService()
        data = [{"id": 1}, {"id": 2}]

        result = service.create_schema_data(data)

        assert result.data == data
        assert result.history == []
        assert result.current_schema is None

    def test_create_schema_data_with_nested_structure(self):
        """Test creating SchemaData from nested JSON structure."""
        service = SchemaService()
        data = {"users": [{"name": "Alice"}, {"name": "Bob"}], "count": 2}

        result = service.create_schema_data(data)

        assert result.data == data
        assert result.history == []
        assert result.current_schema is None

    def test_create_schema_data_with_empty_dict(self):
        """Test creating SchemaData from an empty dictionary."""
        service = SchemaService()
        data: dict = {}

        result = service.create_schema_data(data)

        assert result.data == {}
        assert result.history == []

    def test_create_schema_data_with_empty_list(self):
        """Test creating SchemaData from an empty list."""
        service = SchemaService()
        data: list = []

        result = service.create_schema_data(data)

        assert result.data == []
        assert result.history == []


class TestSchemaServiceValidate:
    """Tests for SchemaService.validate()."""

    @pytest.fixture
    def simple_schema(self) -> Schema:
        """Create a simple schema with one validation rule."""
        return Schema(
            name="test",
            description="Test schema",
            json_schema={"type": "object"},
            validations=[Validation(name="check", description="Check", jq_expression=".x > 0")],
        )

    def test_validate_records_event_in_history(self, simple_schema):
        """Test that validate() records a ValidationEvent in history."""
        service = StubSchemaService()
        schema_data = SchemaData(data={"x": 1}, history=[])

        result = service.validate(schema_data, simple_schema)

        assert len(result.history) == 1
        assert isinstance(result.history[0], ValidationEvent)
        assert result.history[0].schema_ == simple_schema
        assert result.current_schema == simple_schema

    def test_validate_preserves_existing_history(self):
        """Test that validate() preserves existing history events."""
        service = StubSchemaService()
        old_schema = Schema(name="old", description="Old", json_schema={"type": "object"})
        existing_event = ValidationEvent(
            schema=old_schema,
            results=[],
            timestamp=datetime.now(pytz.utc),
        )
        schema_data = SchemaData(data={"x": 1}, history=[existing_event])

        new_schema = Schema(name="new", description="New", json_schema={"type": "object"})
        result = service.validate(schema_data, new_schema)

        assert len(result.history) == 2
        assert result.history[0] == existing_event
        assert isinstance(result.history[1], ValidationEvent)

    def test_validate_records_all_validation_results(self):
        """Test that validate() records results for all validation rules."""
        service = StubSchemaService(
            validation_results={
                "check1": (True, "Passed"),
                "check2": (False, "Failed: value is negative"),
            }
        )
        schema = Schema(
            name="test",
            description="Test",
            json_schema={"type": "object"},
            validations=[
                Validation(name="check1", description="First", jq_expression=".a > 0"),
                Validation(name="check2", description="Second", jq_expression=".b > 0"),
            ],
        )
        schema_data = SchemaData(data={"a": 1, "b": -1}, history=[])

        result = service.validate(schema_data, schema)

        event = result.history[0]
        assert isinstance(event, ValidationEvent)
        assert len(event.results) == 2
        assert event.results[0].passed is True
        assert event.results[0].message == "Passed"
        assert event.results[1].passed is False
        assert event.results[1].message == "Failed: value is negative"

    def test_validate_with_no_validation_rules(self):
        """Test that validate() works with schemas having no validation rules."""
        service = StubSchemaService()
        schema = Schema(name="empty", description="No rules", json_schema={"type": "object"})
        schema_data = SchemaData(data={"x": 1}, history=[])

        result = service.validate(schema_data, schema)

        assert len(result.history) == 1
        event = result.history[0]
        assert isinstance(event, ValidationEvent)
        assert event.results == []
        assert result.is_valid is True

    def test_validate_does_not_mutate_original(self, simple_schema):
        """Test that validate() returns a new SchemaData without mutating the original."""
        service = StubSchemaService()
        original = SchemaData(data={"x": 1}, history=[])

        result = service.validate(original, simple_schema)

        assert original.history == []
        assert len(result.history) == 1
        assert original is not result

    def test_validate_event_has_timestamp(self, simple_schema):
        """Test that the ValidationEvent has a timestamp."""
        service = StubSchemaService()
        schema_data = SchemaData(data={"x": 1}, history=[])

        before = datetime.now(pytz.utc)
        result = service.validate(schema_data, simple_schema)
        after = datetime.now(pytz.utc)

        event = result.history[0]
        assert isinstance(event, ValidationEvent)
        assert before <= event.timestamp <= after

    def test_validate_preserves_data(self, simple_schema):
        """Test that validate() preserves the original data unchanged."""
        service = StubSchemaService()
        data = {"x": 1, "nested": {"a": "b"}}
        schema_data = SchemaData(data=data, history=[])

        result = service.validate(schema_data, simple_schema)

        assert result.data == data


class TestSchemaServiceTransform:
    """Tests for SchemaService.transform()."""

    @pytest.fixture
    def source_schema(self) -> Schema:
        """Create a source schema."""
        return Schema(name="source", description="Source", json_schema={"type": "object"})

    @pytest.fixture
    def target_schema(self) -> Schema:
        """Create a target schema."""
        return Schema(name="target", description="Target", json_schema={"type": "object"})

    @pytest.fixture
    def transformation(self) -> Transformation:
        """Create a transformation."""
        return Transformation(target_schema_name="target", jq_expression=".")

    def test_transform_records_event_in_history(self, source_schema, target_schema, transformation):
        """Test that transform() records a TransformationEvent in history."""
        service = StubSchemaServiceForTransform()
        schema_data = SchemaData(data={"x": 1}, history=[])

        result = service.transform(schema_data, transformation, source_schema, target_schema)

        assert len(result.history) == 1
        assert isinstance(result.history[0], TransformationEvent)
        assert result.history[0].source_schema == source_schema
        assert result.history[0].target_schema == target_schema

    def test_transform_updates_data_with_result(self, source_schema, target_schema, transformation):
        """Test that transform() updates data with the transformation result."""
        service = StubSchemaServiceForTransform(transform_result=({"new_field": "new_value"}, None))
        schema_data = SchemaData(data={"old_field": "old_value"}, history=[])

        result = service.transform(schema_data, transformation, source_schema, target_schema)

        assert result.data == {"new_field": "new_value"}

    def test_transform_sets_current_schema_when_conforms(self, source_schema, target_schema, transformation):
        """Test that transform() sets current_schema to target when data conforms."""
        service = StubSchemaServiceForTransform(conformance_result=(True, "OK"))
        schema_data = SchemaData(data={}, history=[])

        result = service.transform(schema_data, transformation, source_schema, target_schema)

        assert result.current_schema == target_schema

    def test_transform_clears_current_schema_when_not_conforms(self, source_schema, target_schema, transformation):
        """Test that transform() sets current_schema to None when data doesn't conform."""
        service = StubSchemaServiceForTransform(conformance_result=(False, "Does not match target schema"))
        schema_data = SchemaData(data={}, history=[])

        result = service.transform(schema_data, transformation, source_schema, target_schema)

        assert result.current_schema is None

    def test_transform_records_conformance_in_event(self, source_schema, target_schema, transformation):
        """Test that transform() records conformance status in the event."""
        service = StubSchemaServiceForTransform(conformance_result=(False, "Missing required field"))
        schema_data = SchemaData(data={}, history=[])

        result = service.transform(schema_data, transformation, source_schema, target_schema)

        event = result.history[0]
        assert isinstance(event, TransformationEvent)
        assert event.conforms_to_target is False
        assert event.message == "Missing required field"

    def test_transform_raises_on_transformation_error(self, source_schema, target_schema, transformation):
        """Test that transform() raises ValueError when transformation fails."""
        service = StubSchemaServiceForTransform(transform_result=(None, "JQ parse error"))
        schema_data = SchemaData(data={}, history=[])

        with pytest.raises(ValueError, match="Transformation failed: JQ parse error"):
            service.transform(schema_data, transformation, source_schema, target_schema)

    def test_transform_preserves_existing_history(self, source_schema, target_schema, transformation):
        """Test that transform() preserves existing history events."""
        service = StubSchemaServiceForTransform()
        existing_event = ValidationEvent(
            schema=source_schema,
            results=[],
            timestamp=datetime.now(pytz.utc),
        )
        schema_data = SchemaData(data={}, history=[existing_event])

        result = service.transform(schema_data, transformation, source_schema, target_schema)

        assert len(result.history) == 2
        assert result.history[0] == existing_event
        assert isinstance(result.history[1], TransformationEvent)

    def test_transform_does_not_mutate_original(self, source_schema, target_schema, transformation):
        """Test that transform() returns a new SchemaData without mutating the original."""
        service = StubSchemaServiceForTransform()
        original = SchemaData(data={"x": 1}, history=[])

        result = service.transform(original, transformation, source_schema, target_schema)

        assert original.history == []
        assert len(result.history) == 1
        assert original is not result

    def test_transform_event_has_timestamp(self, source_schema, target_schema, transformation):
        """Test that the TransformationEvent has a timestamp."""
        service = StubSchemaServiceForTransform()
        schema_data = SchemaData(data={}, history=[])

        before = datetime.now(pytz.utc)
        result = service.transform(schema_data, transformation, source_schema, target_schema)
        after = datetime.now(pytz.utc)

        event = result.history[0]
        assert isinstance(event, TransformationEvent)
        assert before <= event.timestamp <= after


class TestDocumentServiceInit:
    """Tests for DocumentService initialization and validation."""

    def test_document_service_requires_reducto_url(self):
        """Test that DocumentService raises error when reducto_url is empty."""
        with pytest.raises(ValueError, match="reducto_url must be provided"):
            DocumentService(reducto_url="", reducto_api_key="test-key")

    def test_document_service_requires_reducto_api_key(self):
        """Test that DocumentService raises error when reducto_api_key is empty."""
        with pytest.raises(ValueError, match="reducto_api_key must be provided"):
            DocumentService(reducto_url="https://example.com", reducto_api_key="")

    def test_document_service_accepts_valid_params(self):
        """Test that DocumentService accepts valid parameters."""
        service = DocumentService(
            reducto_url="https://backend.sema4.ai/reducto",
            reducto_api_key="test-api-key",
        )

        assert service._reducto_url == "https://backend.sema4.ai/reducto"
        assert service._reducto_api_key == "test-api-key"
        assert service._client is None  # Lazy initialization

    def test_document_service_uses_default_url(self):
        """Test that DocumentService uses default URL when not overridden."""
        service = DocumentService(reducto_api_key="test-api-key")

        assert service._reducto_url == "https://backend.sema4.ai/reducto"


class TestDocumentServiceStartExtractValidation:
    """Tests for DocumentService.start_extract() validation logic."""

    @pytest.fixture
    def service(self) -> DocumentService:
        """Create a DocumentService instance for testing."""
        return DocumentService(
            reducto_url="https://test.example.com",
            reducto_api_key="test-key",
        )

    @pytest.mark.asyncio
    async def test_start_extract_raises_if_schema_has_no_document_extraction(self, service):
        """Test that start_extract() raises error when schema has no document_extraction."""
        from unittest.mock import MagicMock

        from sema4ai_docint.extraction.reducto.async_ import JobType

        schema = Schema(
            name="no_extraction",
            description="No extraction hints",
            json_schema={"type": "object"},
            document_extraction=None,
        )
        mock_job = MagicMock()
        mock_job.job_type = JobType.PARSE

        with pytest.raises(ValueError, match="has no document extraction hints"):
            await service.start_extract(mock_job, schema)

    @pytest.mark.asyncio
    async def test_start_extract_raises_if_job_is_not_parse_job(self, service):
        """Test that start_extract() raises error when job is not a parse job."""
        from unittest.mock import MagicMock

        from sema4ai_docint.extraction.reducto.async_ import JobType

        from agent_platform.core.semantic_data_model.schemas import DocumentExtraction

        schema = Schema(
            name="with_extraction",
            description="Has extraction hints",
            json_schema={"type": "object"},
            document_extraction=DocumentExtraction(),
        )
        mock_job = MagicMock()
        mock_job.job_type = JobType.EXTRACT

        with pytest.raises(ValueError, match="requires a Parse job"):
            await service.start_extract(mock_job, schema)
