import json

import pytest

from sema4ai_docint.services.exceptions import LayoutServiceError


class TestLayoutService:
    @pytest.mark.parametrize(
        "agent_dummy_server",
        [
            [
                json.dumps(
                    [
                        {
                            "source": "invoice_number",
                            "target": "invoice_number",
                            "transform": "str",
                        },
                        {
                            "source": "total",
                            "target": "total_amount",
                            "transform": "str",
                        },
                        {
                            "source": "items",
                            "target": "line_items",
                            "mode": "flatten",
                        },
                    ]
                )
            ]
        ],
        indirect=True,
    )
    def test_generate_translation_schema_success(
        self,
        setup_db,
        layout_service,
        setup_data_model,
        agent_dummy_server,
        cleanup_db,
    ):
        """Test successful translation schema generation using AgentDummyServer."""
        data_model = setup_data_model

        layout_schema = json.dumps(
            {
                "type": "object",
                "properties": {
                    "invoice_number": {"type": "string"},
                    "total": {"type": "string"},
                    "items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "description": {"type": "string"},
                                "amount": {"type": "string"},
                            },
                        },
                    },
                },
            }
        )

        result = layout_service.generate_translation_schema(
            data_model_name=data_model.name, layout_schema=layout_schema
        )

        assert result is not None
        assert "rules" in result
        assert len(result["rules"]) == 3

    def test_generate_translation_schema_data_model_not_found(
        self, layout_service, agent_dummy_server, drop_mindsdb_views
    ):
        """Test translation schema generation when data model doesn't exist - no agent
        server call needed."""
        layout_schema = json.dumps({"type": "object", "properties": {"test": {"type": "string"}}})

        with pytest.raises(LayoutServiceError, match="Failed to generate translation schema"):
            layout_service.generate_translation_schema(
                data_model_name="non_existent_model", layout_schema=layout_schema
            )

    @pytest.mark.parametrize("agent_dummy_server", [["Error: Agent client error"]], indirect=True)
    def test_generate_translation_schema_agent_client_failure(
        self,
        setup_db,
        layout_service,
        setup_data_model,
        agent_dummy_server,
        cleanup_db,
    ):
        """Test translation schema generation when agent server returns error."""
        data_model = setup_data_model

        layout_schema = json.dumps({"type": "object", "properties": {"test": {"type": "string"}}})

        with pytest.raises(LayoutServiceError, match="Failed to generate translation schema"):
            layout_service.generate_translation_schema(
                data_model_name=data_model.name, layout_schema=layout_schema
            )

    @pytest.mark.parametrize(
        "agent_dummy_server", [[json.dumps({"error": "not a list"})]], indirect=True
    )
    def test_generate_translation_schema_invalid_mapping_response(
        self,
        setup_db,
        layout_service,
        setup_data_model,
        agent_dummy_server,
        cleanup_db,
    ):
        """Test translation schema generation with invalid mapping response from agent server."""
        data_model = setup_data_model

        layout_schema = json.dumps({"type": "object", "properties": {"test": {"type": "string"}}})

        with pytest.raises(LayoutServiceError, match="Failed to generate translation schema"):
            layout_service.generate_translation_schema(
                data_model_name=data_model.name, layout_schema=layout_schema
            )

    @pytest.mark.parametrize(
        "agent_dummy_server",
        [
            [
                json.dumps(
                    [
                        {
                            "source": "invoice_num",
                            "target": "invoice_number",
                            "transform": "str",
                        },
                        {
                            "source": "total_cost",
                            "target": "total",
                            "transform": "float",
                        },
                        {
                            "source": "line_items",
                            "target": "items",
                            "mode": "flatten",
                            "extras": {
                                "item_name": "description",
                                "cost": "amount",
                                "qty": "quantity",
                            },
                        },
                    ]
                )
            ]
        ],
        indirect=True,
    )
    def test_generate_translation_schema_with_complex_mapping(
        self,
        setup_db,
        layout_service,
        setup_data_model,
        agent_dummy_server,
        cleanup_db,
    ):
        """Test translation schema generation with complex mapping rules using AgentDummyServer."""
        data_model = setup_data_model

        layout_schema = json.dumps(
            {
                "type": "object",
                "properties": {
                    "invoice_num": {"type": "string"},
                    "total_cost": {"type": "string"},
                    "line_items": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "item_name": {"type": "string"},
                                "cost": {"type": "string"},
                                "qty": {"type": "number"},
                            },
                        },
                    },
                },
            }
        )

        result = layout_service.generate_translation_schema(
            data_model_name=data_model.name, layout_schema=layout_schema
        )

        assert result is not None
        assert "rules" in result
        assert len(result["rules"]) == 3

        rules = result["rules"]
        flatten_rule = next(rule for rule in rules if rule.get("mode") == "flatten")
        assert "extras" in flatten_rule
        assert len(flatten_rule["extras"]) == 3
