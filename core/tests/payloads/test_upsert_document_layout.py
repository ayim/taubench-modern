import pytest

from agent_platform.core.errors import PlatformHTTPError
from agent_platform.core.payloads.upsert_document_layout import (
    DocumentLayoutPayload,
    _TranslationRule,
    _TranslationSchema,
)


class TestTranslationRule:
    """Test the _TranslationRule class and its model_validate method."""

    def test_model_validate_with_dict(self):
        """Test model_validate with dictionary input."""
        rule_data = {
            "mode": "rename",
            "source": "total",
            "target": "grand_total",
            "extras": {"key": "value"},
            "transform": "upper",
        }

        rule = _TranslationRule.model_validate(rule_data)

        assert rule.mode == "rename"
        assert rule.source == "total"
        assert rule.target == "grand_total"
        assert rule.extras == {"key": "value"}
        assert rule.transform == "upper"

    def test_model_validate_with_object(self):
        """Test model_validate with object that has __dict__ attribute."""

        class RuleObject:
            def __init__(self):
                self.mode = "copy"
                self.source = "field1"
                self.target = "field2"

        rule_obj = RuleObject()
        rule = _TranslationRule.model_validate(rule_obj)

        assert rule.mode == "copy"
        assert rule.source == "field1"
        assert rule.target == "field2"
        assert rule.extras is None
        assert rule.transform is None

    def test_model_validate_with_partial_data(self):
        """Test model_validate with partial data (some fields missing)."""
        rule_data = {"source": "name", "target": "full_name"}

        rule = _TranslationRule.model_validate(rule_data)

        assert rule.mode is None
        assert rule.source == "name"
        assert rule.target == "full_name"
        assert rule.extras is None
        assert rule.transform is None

    def test_model_validate_with_empty_dict(self):
        """Test model_validate with empty dictionary."""
        rule = _TranslationRule.model_validate({})

        assert rule.mode is None
        assert rule.source is None
        assert rule.target is None
        assert rule.extras is None
        assert rule.transform is None


class TestTranslationSchema:
    """Test the _TranslationSchema class and its model_validate method."""

    def test_model_validate_with_rules_dict(self):
        """Test model_validate with dictionary containing 'rules' key."""
        schema_data = {
            "rules": [
                {"mode": "rename", "source": "total", "target": "grand_total"},
                {"mode": "copy", "source": "name", "target": "customer_name"},
            ]
        }

        schema = _TranslationSchema.model_validate(schema_data)

        assert len(schema.rules) == 2
        assert schema.rules[0].mode == "rename"
        assert schema.rules[0].source == "total"
        assert schema.rules[0].target == "grand_total"
        assert schema.rules[1].mode == "copy"
        assert schema.rules[1].source == "name"
        assert schema.rules[1].target == "customer_name"

    def test_model_validate_with_object_having_rules(self):
        """Test model_validate with object that has __dict__ with 'rules'."""

        class SchemaObject:
            def __init__(self):
                self.rules = [{"source": "field1", "target": "field2"}]

        schema_obj = SchemaObject()
        schema = _TranslationSchema.model_validate(schema_obj)

        assert len(schema.rules) == 1
        assert schema.rules[0].source == "field1"
        assert schema.rules[0].target == "field2"

    def test_model_validate_missing_rules_key_raises_error(self):
        """Test that missing 'rules' key raises PlatformHTTPError."""
        schema_data = {"other_key": "value"}

        with pytest.raises(PlatformHTTPError) as exc_info:
            _TranslationSchema.model_validate(schema_data)

        assert exc_info.value.status_code == 400  # BAD_REQUEST
        assert "Translation schema must be an object with a `rules` key" in str(exc_info.value)

    def test_model_validate_empty_dict_raises_error(self):
        """Test that empty dictionary raises PlatformHTTPError."""
        with pytest.raises(PlatformHTTPError) as exc_info:
            _TranslationSchema.model_validate({})

        assert exc_info.value.status_code == 400  # BAD_REQUEST
        assert "Translation schema must be an object with a `rules` key" in str(exc_info.value)

    def test_model_validate_with_empty_rules_list(self):
        """Test model_validate with empty rules list."""
        schema_data = {"rules": []}

        schema = _TranslationSchema.model_validate(schema_data)

        assert len(schema.rules) == 0

    def test_to_compact_dict(self):
        """Test to_compact_dict method."""
        schema_data = {
            "rules": [
                {"mode": "rename", "source": "total", "target": "grand_total"},
                {"source": "name", "target": "customer_name"},  # partial rule
            ]
        }

        schema = _TranslationSchema.model_validate(schema_data)
        compact = schema.to_compact_dict()

        assert "rules" in compact
        assert len(compact["rules"]) == 2
        assert compact["rules"][0]["mode"] == "rename"
        assert compact["rules"][0]["source"] == "total"
        assert compact["rules"][0]["target"] == "grand_total"
        assert compact["rules"][1]["source"] == "name"
        assert compact["rules"][1]["target"] == "customer_name"
        # Check that None values are not included in compact dict
        assert "mode" not in compact["rules"][1]


class TestDocumentLayoutPayload:
    """Test the DocumentLayoutPayload class and its model_validate method."""

    def test_model_validate_with_translation_schema_as_list(self):
        """Test model_validate with translation_schema as list (should be wrapped)."""
        payload_data = {
            "name": "test-layout",
            "data_model_name": "test-model",
            "extraction_schema": {"type": "object"},
            "translation_schema": [
                {"mode": "rename", "source": "total", "target": "grand_total"},
                {"mode": "copy", "source": "name", "target": "customer_name"},
            ],
            "summary": "Test layout",
        }

        payload = DocumentLayoutPayload.model_validate(payload_data)

        assert payload.name == "testlayout"  # normalized (hyphens removed)
        assert payload.data_model_name == "testmodel"  # normalized (hyphens removed)
        assert payload.extraction_schema == {"type": "object"}
        assert payload.summary == "Test layout"

        # Check that list was converted to _TranslationSchema
        assert isinstance(payload.translation_schema, _TranslationSchema)
        assert len(payload.translation_schema.rules) == 2
        assert payload.translation_schema.rules[0].mode == "rename"
        assert payload.translation_schema.rules[0].source == "total"
        assert payload.translation_schema.rules[0].target == "grand_total"

    def test_model_validate_with_translation_schema_as_dict(self):
        """Test model_validate with translation_schema as dictionary with 'rules' key."""
        payload_data = {
            "name": "test-layout",
            "data_model_name": "test-model",
            "extraction_schema": {"type": "object"},
            "translation_schema": {
                "rules": [
                    {"mode": "rename", "source": "total", "target": "grand_total"},
                    {"mode": "copy", "source": "name", "target": "customer_name"},
                ]
            },
            "summary": "Test layout",
        }

        payload = DocumentLayoutPayload.model_validate(payload_data)

        assert payload.name == "testlayout"  # normalized (hyphens removed)
        assert payload.data_model_name == "testmodel"  # normalized (hyphens removed)
        assert payload.extraction_schema == {"type": "object"}
        assert payload.summary == "Test layout"

        # Check that dictionary was processed correctly
        assert isinstance(payload.translation_schema, _TranslationSchema)
        assert len(payload.translation_schema.rules) == 2
        assert payload.translation_schema.rules[0].mode == "rename"
        assert payload.translation_schema.rules[0].source == "total"
        assert payload.translation_schema.rules[0].target == "grand_total"

    def test_model_validate_with_no_translation_schema(self):
        """Test model_validate with no translation_schema provided."""
        payload_data = {
            "name": "test-layout",
            "data_model_name": "test-model",
            "extraction_schema": {"type": "object"},
        }

        payload = DocumentLayoutPayload.model_validate(payload_data)

        assert payload.translation_schema is None

    def test_model_validate_with_empty_translation_schema(self):
        """Test model_validate with empty/falsy translation_schema."""
        payload_data = {
            "name": "test-layout",
            "data_model_name": "test-model",
            "extraction_schema": {"type": "object"},
            "translation_schema": None,
        }

        payload = DocumentLayoutPayload.model_validate(payload_data)

        assert payload.translation_schema is None

    def test_model_validate_name_normalization(self):
        """Test that names are properly normalized."""
        payload_data = {
            "name": "Test Layout V1!!",
            "data_model_name": "Test Model Name!!",
            "extraction_schema": {"type": "object"},
        }

        payload = DocumentLayoutPayload.model_validate(payload_data)

        # Names should be normalized (spaces -> underscores, special chars removed, lowercase)
        assert payload.name == "test_layout_v1"
        assert payload.data_model_name == "test_model_name"

    def test_model_validate_with_all_fields(self):
        """Test model_validate with all possible fields."""
        payload_data = {
            "name": "comprehensive-layout",
            "data_model_name": "comprehensive-model",
            "extraction_schema": {"type": "object", "properties": {"field1": {"type": "string"}}},
            "translation_schema": [{"source": "field1", "target": "output1"}],
            "summary": "Comprehensive test layout",
            "extraction_config": {"mode": "strict", "threshold": 0.9},
            "prompt": "Custom system prompt",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-02T00:00:00Z",
        }

        payload = DocumentLayoutPayload.model_validate(payload_data)

        assert payload.name == "comprehensivelayout"
        assert payload.data_model_name == "comprehensivemodel"
        assert payload.extraction_schema == {
            "type": "object",
            "properties": {"field1": {"type": "string"}},
        }
        assert isinstance(payload.translation_schema, _TranslationSchema)
        assert payload.summary == "Comprehensive test layout"
        assert payload.extraction_config == {"mode": "strict", "threshold": 0.9}
        assert payload.prompt == "Custom system prompt"
        assert payload.created_at == "2024-01-01T00:00:00Z"
        assert payload.updated_at == "2024-01-02T00:00:00Z"

    def test_wrap_translation_schema_with_translation_schema_object(self):
        """Test wrap_translation_schema method with _TranslationSchema object."""
        payload_data = {
            "name": "test-layout",
            "data_model_name": "test-model",
            "translation_schema": {"rules": [{"source": "field1", "target": "output1"}]},
        }

        payload = DocumentLayoutPayload.model_validate(payload_data)
        wrapped = payload.wrap_translation_schema()

        assert wrapped == {"rules": [{"source": "field1", "target": "output1"}]}

    def test_wrap_translation_schema_with_list_of_rules(self):
        """Test wrap_translation_schema method with list of _TranslationRule objects."""
        # Create a payload where translation_schema ends up as a list
        # This can happen in some edge cases or manual construction
        payload_data = {
            "name": "test-layout",
            "data_model_name": "test-model",
            "translation_schema": [{"source": "field1", "target": "output1"}],
        }

        payload = DocumentLayoutPayload.model_validate(payload_data)

        # The model_validate should convert list to _TranslationSchema
        assert isinstance(payload.translation_schema, _TranslationSchema)

        wrapped = payload.wrap_translation_schema()
        assert wrapped == {"rules": [{"source": "field1", "target": "output1"}]}

    def test_wrap_translation_schema_with_none(self):
        """Test wrap_translation_schema method with None."""
        payload_data = {
            "name": "test-layout",
            "data_model_name": "test-model",
        }

        payload = DocumentLayoutPayload.model_validate(payload_data)
        wrapped = payload.wrap_translation_schema()

        assert wrapped is None
