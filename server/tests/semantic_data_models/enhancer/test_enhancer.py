"""Unit tests for semantic data model enhancer."""

import pytest


def test_create_semantic_data_model_for_llm_from_semantic_data_model(data_regression):
    """Test creating a semantic data model for LLM from a semantic data model."""
    from agent_platform.core.data_frames.semantic_data_model_types import (
        BaseTable,
        Dimension,
        Filter,
        LogicalTable,
        SemanticDataModel,
        TimeDimension,
    )
    from agent_platform.server.semantic_data_models.enhancer.parse import (
        update_semantic_data_model_with_semantic_data_model_from_llm,
    )
    from agent_platform.server.semantic_data_models.enhancer.type_defs import (
        create_semantic_data_model_for_llm_from_semantic_data_model,
    )

    dimension_example_1: Dimension = {
        "name": "product_category",
        "synonyms": ["item_category", "product_type"],
        "description": "The category of the product sold.",
        "expr": "cat",
        "data_type": "NUMBER",
        "unique": False,
        "sample_values": ["501", "544"],
    }

    dimension_example_2: Dimension = {
        "name": "store_country",
        "description": "The country where the sale took place.",
        "expr": "cntry",
        "data_type": "TEXT",
        "unique": False,
        "sample_values": ["USA", "GBR"],
    }

    dimensions_example: list[Dimension] = [
        dimension_example_1,
        dimension_example_2,
    ]

    base_table_example: BaseTable = {"database": "sales", "schema": "public", "table": "sd_data"}

    time_dimensions_example: list[TimeDimension] = [
        {
            "name": "sale_timestamp",
            "synonyms": ["time_of_sale", "transaction_time"],
            "description": "The time when the sale occurred. In UTC.",
            "expr": "dt",
            "data_type": "TIMESTAMP",
            "unique": False,
        }
    ]

    filter_example_1: Filter = {
        "name": "north_america",
        "synonyms": ["North America", "N.A.", "NA"],
        "description": "A filter to restrict only to north american countries",
        "expr": "cntry IN ('canada', 'mexico', 'usa')",
    }

    tables_example: list[LogicalTable] = [
        {
            "name": "sales_data",
            "description": """A logical table capturing daily sales information across different
                store locations and product categories.""",
            "base_table": base_table_example,
            "dimensions": dimensions_example,
            "time_dimensions": time_dimensions_example,
            "facts": [],
            "filters": [
                filter_example_1,
            ],
        }
    ]

    semantic_model_example: SemanticDataModel = {
        "name": "Sales Data",
        "description": "This semantic model can be used for asking questions over the sales data.",
        "tables": tables_example,
    }

    semantic_data_model_for_llm = create_semantic_data_model_for_llm_from_semantic_data_model(
        semantic_model_example
    )

    data_regression.check(semantic_data_model_for_llm.model_dump())

    # Now, add some synonyms and change the categories of some columns
    assert semantic_data_model_for_llm.tables
    table = semantic_data_model_for_llm.tables[0]
    assert table.columns
    table.columns[0].category = "fact"
    table.columns[0].synonyms = [
        "product_category_synonym1",
        "product_category_synonym2",
    ]

    table.columns[1].category = "dimension"
    table.columns[1].synonyms = [
        "store_country_synonym1",
        "store_country_synonym2",
    ]

    table.columns[2].synonyms = [
        "sales_channel_synonym1",
        "sales_channel_synonym2",
    ]
    data_regression.check(semantic_data_model_for_llm.model_dump(), basename="changed_for_llm")

    update_semantic_data_model_with_semantic_data_model_from_llm(
        semantic_model_example, semantic_data_model_for_llm
    )
    data_regression.check(semantic_model_example, basename="updated_from_llm")

    # Recreating it for the LLM should give the same result
    semantic_data_model_for_llm = create_semantic_data_model_for_llm_from_semantic_data_model(
        semantic_model_example
    )
    data_regression.check(semantic_data_model_for_llm.model_dump(), basename="changed_for_llm")

    update_semantic_data_model_with_semantic_data_model_from_llm(
        semantic_model_example, semantic_data_model_for_llm
    )
    data_regression.check(semantic_model_example, basename="updated_from_llm")


def test_output_schema_format(file_regression):
    """Test the output schema format."""
    from agent_platform.server.semantic_data_models.enhancer.type_defs import (
        FULL_OUTPUT_SCHEMA_FORMAT,
    )

    file_regression.check(FULL_OUTPUT_SCHEMA_FORMAT, basename="output_schema_format")


@pytest.mark.asyncio
async def test_enhance_semantic_data_model_with_invalid_json_retry():
    """Test enhancing a semantic data model when LLM first returns invalid JSON.

    This unit test verifies that invalid JSON responses are handled correctly through
    retry logic. It mocks prompt_generate to return:
    1. First call: improperly formatted JSON response (missing closing brace)
    2. Second call: valid JSON response

    The system should:
    - Detect invalid JSON parsing
    - Request correction by adding error message to the prompt
    - Parse the corrected JSON response successfully
    - Successfully enhance the model

    Note: Quality check is disabled by default, so only 2 calls are expected.
    """
    from unittest.mock import MagicMock, patch

    from agent_platform.core.payloads.semantic_data_model_payloads import (
        ColumnInfo,
        DataConnectionInfo,
        TableInfo,
    )
    from agent_platform.core.responses.content.text import ResponseTextContent
    from agent_platform.core.responses.response import ResponseMessage
    from agent_platform.core.user import User
    from agent_platform.server.kernel.semantic_data_model_generator import (
        SemanticDataModelGenerator,
    )

    # Create a simple semantic model to enhance
    mock_storage = MagicMock()
    mock_user = User(user_id="test_user", sub="test_user")

    # Create a simple semantic model to enhance with user, storage, and agent_id
    generator = SemanticDataModelGenerator()

    column_info = ColumnInfo(
        name="system_name",
        data_type="TEXT",
        sample_values=["GPT-4", "Claude-2", "Gemini"],
    )

    table_info = TableInfo(
        name="ai_systems",
        database="test_db",
        schema="public",
        columns=[column_info],
    )

    data_connection_info = DataConnectionInfo(
        data_connection_id="conn_123",
        tables_info=[table_info],
    )

    semantic_model = await generator.generate_semantic_data_model(
        name="test_model",
        description="Test semantic model",
        data_connections_info=[data_connection_info],
        files_info=[],
    )
    # Save the original table name for later comparison
    original_table_name = semantic_model["tables"][0].get("name")  # type: ignore[index]
    assert original_table_name is not None
    assert original_table_name == "ai_systems"

    # First response: improperly formatted JSON (missing closing braces)
    invalid_json_response = """<semantic-data-model>
{
  "name": "test_model",
  "description": "Enhanced test semantic model",
  "tables": [
    {
      "name": "ai_systems_enhanced",
      "base_table": {
        "table": "ai_systems",
        "schema": "public"
      },
      "columns": [
        {
          "name": "system_name",
          "expr": "system_name",
          "data_type": "TEXT",
          "category": "dimension",
          "description": "Name of the AI system"
        }
      ]
    }
</semantic-data-model>"""

    # Second response: valid JSON response
    valid_json_response = """<semantic-data-model>
{
  "name": "test_model",
  "description": "Enhanced test semantic model",
  "tables": [
    {
      "name": "ai_systems_enhanced",
      "base_table": {
        "table": "ai_systems",
        "schema": "public"
      },
      "columns": [
        {
          "name": "system_name",
          "expr": "system_name",
          "data_type": "TEXT",
          "category": "dimension",
          "description": "Name of the AI system",
          "synonyms": ["ai_name", "model_name"]
        }
      ]
    }
  ]
}
</semantic-data-model>"""

    # Track which call we're on
    call_count = [0]

    async def mock_prompt_generate(*args, **kwargs):
        """Mock that returns invalid JSON first, then valid JSON."""
        call_count[0] += 1
        if call_count[0] == 1:
            # First call: return invalid JSON response
            return ResponseMessage(
                role="agent",
                content=[ResponseTextContent(text=invalid_json_response)],
            )
        elif call_count[0] == 2:
            # Second call: return valid JSON response
            return ResponseMessage(
                role="agent",
                content=[ResponseTextContent(text=valid_json_response)],
            )
        else:
            pytest.fail(f"Unexpected call {call_count[0]} to prompt_generate")
            return None  # Type hint satisfaction

    # Patch prompt_generate at the module where it's imported
    with patch(
        "agent_platform.server.api.private_v2.prompt.prompt_generate",
        new=mock_prompt_generate,
    ):
        from agent_platform.server.semantic_data_models.enhancer.enhancer import (
            SemanticDataModelEnhancer,
        )

        enhancer = SemanticDataModelEnhancer(
            user=mock_user,
            storage=mock_storage,
            agent_id="test_agent_id",
        )

        # Call enhance_semantic_data_model
        enhanced_model = await enhancer.enhance_semantic_data_model(
            semantic_model=semantic_model,
        )

        # Verify we got two calls (initial + retry, no quality check since it's disabled by default)
        assert call_count[0] == 2, f"Expected 2 calls to prompt_generate, got {call_count[0]}"

        # Check if the model was actually enhanced
        # Original has table name "ai_systems", enhanced should have "ai_systems_enhanced"
        assert semantic_model.get("tables") is not None
        assert enhanced_model.get("tables") is not None

        enhanced_table_name = enhanced_model["tables"][0].get("name")  # type: ignore[index]

        if original_table_name == enhanced_table_name:
            # The model was NOT enhanced - the retry didn't work
            pytest.fail(
                f"Enhancement failed - invalid JSON was not retried correctly. "
                f"Model unchanged (table name still '{original_table_name}'). "
                f"Expected: 'ai_systems_enhanced', Got: '{enhanced_table_name}'"
            )

        # Enhancement worked! Verify the valid response was parsed correctly
        assert enhanced_table_name == "ai_systems_enhanced", (
            f"Expected table name 'ai_systems_enhanced', got '{enhanced_table_name}'"
        )

        # Verify column was enhanced with description/synonyms from valid response
        dimensions = enhanced_model["tables"][0].get("dimensions")  # type: ignore[index]
        assert dimensions is not None
        assert len(dimensions) > 0
        enhanced_column = dimensions[0]

        description = enhanced_column.get("description")
        assert description == "Name of the AI system", (
            f"Expected description from valid response, got: {description}"
        )

        synonyms = enhanced_column.get("synonyms", [])
        assert synonyms is not None
        assert "ai_name" in synonyms, "Expected 'ai_name' synonym from valid response"
        assert "model_name" in synonyms, "Expected 'model_name' synonym from valid response"
