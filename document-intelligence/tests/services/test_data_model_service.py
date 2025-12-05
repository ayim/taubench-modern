import json
from unittest.mock import Mock, patch

import pytest

from sema4ai_docint.models.data_model import DataModel
from sema4ai_docint.models.document_layout import DocumentLayout
from sema4ai_docint.services.exceptions import DataModelServiceError
from tests.agent_dummy_server import SCHEMA_RESPONSE


class TestDataModelService:
    @pytest.mark.parametrize("agent_dummy_server", [[SCHEMA_RESPONSE]], indirect=True)
    def test_generate_from_file_success(
        self,
        setup_db,
        data_model_service,
        agent_dummy_server,
        cleanup_db,
    ):
        """Test successful schema generation from file using AgentDummyServer."""
        result = data_model_service.generate_from_file("INV-00001.pdf")

        assert result is not None
        assert "message" in result
        assert "schema" in result
        assert result["message"] == "Data model generated successfully"
        assert result["schema"]["type"] == "object"
        assert result["schema"]["title"] == "Invoice"

    def test_generate_from_file_http_request_failure(
        self,
        setup_db,
        data_model_service,
        agent_dummy_server,
        cleanup_db,
    ):
        """Test schema generation when HTTP request fails with non-200 status code."""
        with patch.object(
            data_model_service._context.agent_client,
            "generate_schema",
            side_effect=ValueError("Failed to generate summary: 500 Internal Server Error"),
        ):
            with pytest.raises(
                DataModelServiceError,
                match=(
                    "Failed to generate data model schema: Failed to generate summary: "
                    "500 Internal Server Error"
                ),
            ):
                data_model_service.generate_from_file("INV-00001.pdf")

    @pytest.mark.parametrize(
        "agent_dummy_server",
        [
            [
                "Layout summary for test_model",
            ]
        ],
        indirect=True,
    )
    def test_create_from_schema_success(
        self,
        setup_db,
        data_model_service,
        agent_dummy_server,
        cleanup_db,
        drop_mindsdb_views,
    ):
        """Test successful data model creation from schema using AgentDummyServer."""
        schema = {
            "type": "object",
            "properties": {
                "invoice_number": {"type": "string"},
                "total": {"type": "string"},
            },
        }

        result = data_model_service.create_from_schema(
            name="test_model",
            description="Test data model",
            json_schema_text=json.dumps(schema),
            prompt="Test prompt",
            summary="Test summary",
        )

        assert result is not None
        assert result["name"] == "test_model"
        assert result["description"] == "Test data model"

        assert "model_schema" in result
        assert result["model_schema"] is not None
        assert result["model_schema"]["type"] == "object"
        assert "properties" in result["model_schema"]
        assert "invoice_number" in result["model_schema"]["properties"]
        assert "total" in result["model_schema"]["properties"]

        assert "prompt" in result
        assert result["prompt"] == "Test prompt"
        assert "summary" in result
        assert result["summary"] == "Test summary"

        assert len(result["views"]) > 0

        assert "quality_checks" in result

    @pytest.mark.parametrize(
        "agent_dummy_server",
        [
            [
                "Auto-generated data model summary",
                "Auto-generated layout summary",
            ]
        ],
        indirect=True,
    )
    def test_create_from_schema_with_auto_summary(
        self,
        setup_db,
        data_model_service,
        agent_dummy_server,
        cleanup_db,
        drop_mindsdb_views,
    ):
        """Test data model creation with automatic summary generation using AgentDummyServer."""
        schema = {
            "type": "object",
            "properties": {
                "invoice_number": {"type": "string"},
                "total": {"type": "string"},
            },
        }

        result = data_model_service.create_from_schema(
            name="test_model_auto_summary",
            description="Test data model with auto summary",
            json_schema_text=json.dumps(schema),
            prompt="Test prompt",
        )

        assert result is not None
        assert result["name"] == "test_model_auto_summary"
        assert result["summary"] == "Auto-generated data model summary"

    def test_create_from_schema_duplicate_name(
        self,
        setup_db,
        data_model_service,
        setup_data_model,
        agent_dummy_server,
        cleanup_db,
    ):
        """Test data model creation with duplicate name - no agent server call needed."""
        existing_model = setup_data_model
        schema = {"type": "object", "properties": {"test": {"type": "string"}}}

        with pytest.raises(DataModelServiceError, match="already exists in the system"):
            data_model_service.create_from_schema(
                name=existing_model.name,
                description="Duplicate model",
                json_schema_text=json.dumps(schema),
            )

    def test_create_from_schema_name_normalization(
        self,
        setup_db,
        data_model_service,
        setup_data_model,
        agent_dummy_server,
        cleanup_db,
    ):
        """Test that normalized names are checked for duplicates - no agent server call needed."""
        existing_model = setup_data_model
        schema = {"type": "object", "properties": {"test": {"type": "string"}}}

        # Use a name that normalizes to the existing model name
        denormalized_name = existing_model.name.replace("_", " ").upper()

        with pytest.raises(DataModelServiceError, match="already exists in the system"):
            data_model_service.create_from_schema(
                name=denormalized_name,
                description="Duplicate normalized model",
                json_schema_text=json.dumps(schema),
            )

    def test_create_from_schema_invalid_json(
        self,
        setup_db,
        data_model_service,
        agent_dummy_server,
        cleanup_db,
    ):
        """Test data model creation with invalid JSON schema - no agent server call needed."""
        import json

        with pytest.raises(json.JSONDecodeError):
            data_model_service.create_from_schema(
                name="invalid_model",
                description="Invalid model",
                json_schema_text="invalid json",
            )

    @pytest.mark.parametrize(
        "agent_dummy_server",
        [
            [
                '{"type": "object", "properties": {"test": {"type": "string"}}}',
                "Test summary",
            ]
        ],
        indirect=True,
    )
    def test_create_from_schema_view_creation_failure(
        self,
        setup_db,
        data_model_service,
        context,
        agent_dummy_server,
        cleanup_db,
    ):
        """Test data model creation when view creation fails - needs agent server responses."""
        original_create_business_views = data_model_service.create_business_views
        data_model_service.create_business_views = Mock(
            side_effect=Exception("View creation failed")
        )

        schema = {"type": "object", "properties": {"test": {"type": "string"}}}

        with pytest.raises(DataModelServiceError, match="Failed to create views"):
            data_model_service.create_from_schema(
                name="view_fail_model",
                description="Model with view failure",
                json_schema_text=json.dumps(schema),
            )

        data_model_service.create_business_views = original_create_business_views

        cleanup_model = DataModel.find_by_name(context.datasource, "view_fail_model")
        assert cleanup_model is None

    def test_create_business_views_success(
        self,
        setup_db,
        data_model_service,
        setup_data_model,
        agent_dummy_server,
        cleanup_db,
    ):
        """Test successful business view creation - no agent server call needed."""
        data_model = setup_data_model

        result = data_model_service.create_business_views(data_model.name)

        assert result is not None
        assert "Message" in result
        assert result["Message"] == "Business views created successfully"

        updated_model = DataModel.find_by_name(
            data_model_service._context.datasource, data_model.name
        )
        assert updated_model is not None
        assert updated_model.views is not None

    def test_create_business_views_data_model_not_found(
        self,
        setup_db,
        data_model_service,
        agent_dummy_server,
        cleanup_db,
    ):
        """Test business view creation when data model doesn't exist - no agent server
        call needed."""
        with pytest.raises(DataModelServiceError, match="Data model with name .* not found"):
            data_model_service.create_business_views("non_existent_model")

    def test_create_business_views_view_generation_failure(
        self,
        setup_db,
        data_model_service,
        setup_data_model,
        agent_dummy_server,
        cleanup_db,
    ):
        """Test business view creation when view generation fails - no agent server call needed."""
        from unittest.mock import patch

        data_model = setup_data_model

        with patch("sema4ai_docint.services._data_model.ViewGenerator") as mock_view_generator:
            mock_generator_instance = Mock()
            mock_generator_instance.generate_views.side_effect = Exception("View generation failed")
            mock_view_generator.return_value = mock_generator_instance

            with pytest.raises(DataModelServiceError, match="Error generating .* views"):
                data_model_service.create_business_views(data_model.name)

    @pytest.mark.parametrize("agent_dummy_server", [["Test layout summary"]], indirect=True)
    def test_create_or_update_default_layout_create(
        self,
        setup_db,
        data_model_service,
        context,
        agent_dummy_server,
        cleanup_db,
    ):
        """Test default layout creation using AgentDummyServer."""
        schema = {
            "type": "object",
            "properties": {
                "invoice_number": {"type": "string"},
                "total": {"type": "string"},
            },
        }

        data_model_service._create_or_update_default_layout("test_layout_model", schema, schema)

        layout = DocumentLayout.find_by_name(context.datasource, "test_layout_model", "default")
        assert layout is not None
        assert layout.extraction_schema == schema
        assert "rules" in layout.translation_schema
        assert layout.summary == "Test layout summary"

    @pytest.mark.parametrize("agent_dummy_server", [["Updated layout summary"]], indirect=True)
    def test_create_or_update_default_layout_update(
        self,
        setup_db,
        data_model_service,
        postgres_datasource,
        context,
        agent_dummy_server,
    ):
        """Test default layout update when it already exists using AgentDummyServer."""
        existing_layout = DocumentLayout(
            name="default",
            data_model="test_update_model",
            extraction_schema={"old": "schema"},
            translation_schema={"old": "rules"},
            summary=None,
        )
        existing_layout.insert(postgres_datasource)

        new_schema = {"type": "object", "properties": {"new_field": {"type": "string"}}}

        data_model_service._create_or_update_default_layout(
            "test_update_model", new_schema, new_schema
        )

        updated_layout = DocumentLayout.find_by_name(
            context.datasource, "test_update_model", "default"
        )
        assert updated_layout is not None
        assert updated_layout.extraction_schema == new_schema
        assert updated_layout.summary == "Updated layout summary"

    def test_data_model_service_filter_schemas(self, data_model_service):
        """Test DataModelService._filter_schemas with description and layout_description fields."""

        # Schema with both description and layout_description for every attribute
        schema = {
            "type": "object",
            "properties": {
                "invoice_number": {
                    "type": "string",
                    "description": "Invoice identifier",
                    "layout_description": "Top-right corner of document",
                },
                "total_amount": {
                    "type": "number",
                    "description": "Total invoice amount",
                    "layout_description": "Bottom-right, bold text",
                },
                "line_items": {
                    "type": "array",
                    "description": "Individual line items",
                    "layout_description": "Table called transactions",
                    "items": {
                        "type": "object",
                        "properties": {
                            "item_description": {
                                "type": "string",
                                "description": "Item description",
                                "layout_description": "First column of table",
                            },
                            "amount": {
                                "type": "number",
                                "description": "Item amount",
                                "layout_description": "Last column of table",
                            },
                        },
                    },
                },
            },
        }

        data_model_schema, document_layout_schema = data_model_service._filter_schemas(schema)

        # First return value: has description, no layout_description
        expected_data_model = {
            "type": "object",
            "properties": {
                "invoice_number": {"type": "string", "description": "Invoice identifier"},
                "total_amount": {"type": "number", "description": "Total invoice amount"},
                "line_items": {
                    "type": "array",
                    "description": "Individual line items",
                    "items": {
                        "type": "object",
                        "properties": {
                            "item_description": {
                                "type": "string",
                                "description": "Item description",
                            },
                            "amount": {"type": "number", "description": "Item amount"},
                        },
                    },
                },
            },
        }
        assert data_model_schema == expected_data_model

        # Second return value: description replaced with layout_description values
        # and then layout_description omitted.
        expected_document_layout = {
            "type": "object",
            "properties": {
                "invoice_number": {
                    "type": "string",
                    "description": "Top-right corner of document",
                },
                "total_amount": {
                    "type": "number",
                    "description": "Bottom-right, bold text",
                },
                "line_items": {
                    "type": "array",
                    "description": "Table called transactions",
                    "items": {
                        "type": "object",
                        "properties": {
                            "item_description": {
                                "type": "string",
                                "description": "First column of table",
                            },
                            "amount": {
                                "type": "number",
                                "description": "Last column of table",
                            },
                        },
                    },
                },
            },
        }
        assert document_layout_schema == expected_document_layout
