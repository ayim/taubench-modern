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

    semantic_data_model_for_llm = create_semantic_data_model_for_llm_from_semantic_data_model(semantic_model_example)

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

    update_semantic_data_model_with_semantic_data_model_from_llm(semantic_model_example, semantic_data_model_for_llm)
    data_regression.check(semantic_model_example, basename="updated_from_llm")

    # Recreating it for the LLM should give the same result
    semantic_data_model_for_llm = create_semantic_data_model_for_llm_from_semantic_data_model(semantic_model_example)
    data_regression.check(semantic_data_model_for_llm.model_dump(), basename="changed_for_llm")

    update_semantic_data_model_with_semantic_data_model_from_llm(semantic_model_example, semantic_data_model_for_llm)
    data_regression.check(semantic_model_example, basename="updated_from_llm")


@pytest.mark.asyncio
async def test_enhance_semantic_data_model_with_invalid_json_retry():
    """Test enhancing a semantic data model when LLM text responses are rejected.

    This unit test verifies that text responses (without tool calls) are rejected.
    The system now requires tool calls for all responses.
    """
    from unittest.mock import AsyncMock, MagicMock, patch

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

    # Response without tool call - text response that should be rejected
    text_response = """Here is the enhanced semantic data model with improved names and descriptions."""

    # Create async mock
    mock_prompt_generate = AsyncMock()
    mock_prompt_generate.return_value = ResponseMessage(
        role="agent",
        content=[ResponseTextContent(text=text_response)],
    )

    from agent_platform.server.semantic_data_models.enhancer.enhancer import (
        SemanticDataModelEnhancer,
    )

    # Patch prompt_generate at its source location
    with patch(
        "agent_platform.server.api.private_v2.prompt.prompt_generate",
        mock_prompt_generate,
    ):
        enhancer = SemanticDataModelEnhancer(
            user=mock_user,
            storage=mock_storage,
            agent_id="test_agent_id",
        )

        # Call enhance_semantic_data_model
        enhanced_model = await enhancer.enhance_semantic_data_model(
            semantic_model=semantic_model,
        )

        # Verify that the model was NOT enhanced since text responses are not accepted
        # The enhancer returns the original model unchanged on failure
        original_table_name = semantic_model["tables"][0].get("name")  # type: ignore[index]
        enhanced_table_name = enhanced_model["tables"][0].get("name")  # type: ignore[index]

        assert original_table_name == enhanced_table_name, (
            f"Expected model to remain unchanged when text response is returned, "
            f"but got table name '{enhanced_table_name}'"
        )


@pytest.mark.asyncio
async def test_enhance_semantic_data_model_with_tool_call():
    """Test enhancing a semantic data model using structured tool calls.

    This unit test verifies that tool call responses are handled correctly through
    the new structured tool calling approach. It mocks prompt_generate to return:
    1. First call: invalid tool call (missing required fields)
    2. Second call: valid tool call with complete enhancement

    The system should:
    - Detect schema validation errors in tool calls
    - Request correction by adding error message to the prompt
    - Parse the corrected tool call response successfully
    - Successfully enhance the model

    Note: Quality check is disabled by default, so only 2 calls are expected.
    """
    from unittest.mock import MagicMock, patch

    from agent_platform.core.payloads.semantic_data_model_payloads import (
        ColumnInfo,
        DataConnectionInfo,
        TableInfo,
    )
    from agent_platform.core.responses.content.tool_use import ResponseToolUseContent
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

    # First response: invalid tool call (missing required 'tables' field)
    invalid_tool_input = '{"name": "test_model", "description": "Enhanced test semantic model"}'

    # Second response: valid tool call with complete enhancement
    valid_tool_input = """{
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
}"""

    # Track which call we're on
    call_count = [0]

    async def mock_prompt_generate(*args, **kwargs):
        """Mock that returns invalid tool call first, then valid tool call."""
        call_count[0] += 1
        if call_count[0] == 1:
            # First call: return invalid tool call response
            return ResponseMessage(
                role="agent",
                content=[
                    ResponseToolUseContent(
                        tool_call_id="call_1",
                        tool_name="enhance_semantic_data_model",
                        tool_input_raw=invalid_tool_input,
                    )
                ],
            )
        elif call_count[0] == 2:
            # Second call: return valid tool call response
            return ResponseMessage(
                role="agent",
                content=[
                    ResponseToolUseContent(
                        tool_call_id="call_2",
                        tool_name="enhance_semantic_data_model",
                        tool_input_raw=valid_tool_input,
                    )
                ],
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
                f"Enhancement failed - invalid tool call was not retried correctly. "
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
        assert description == "Name of the AI system", f"Expected description from valid response, got: {description}"

        synonyms = enhanced_column.get("synonyms", [])
        assert synonyms is not None
        assert "ai_name" in synonyms, "Expected 'ai_name' synonym from valid response"
        assert "model_name" in synonyms, "Expected 'model_name' synonym from valid response"


class TestGetDataConnectionTableNames:
    """Tests for _get_data_connection_table_names function."""

    @pytest.mark.asyncio
    async def test_identifies_data_connection_tables(self):
        """Should identify tables with data_connection_id."""
        from agent_platform.core.payloads.semantic_data_model_payloads import (
            ColumnInfo,
            DataConnectionInfo,
            TableInfo,
        )
        from agent_platform.server.kernel.semantic_data_model_generator import (
            SemanticDataModelGenerator,
        )
        from agent_platform.server.semantic_data_models.enhancer.prompts import (
            _get_data_connection_table_names,
        )

        generator = SemanticDataModelGenerator()
        column_info = ColumnInfo(name="col1", data_type="TEXT", sample_values=["a", "b"])
        table_info = TableInfo(
            name="dc_table",
            database="test_db",
            schema="public",
            columns=[column_info],
        )
        data_connection_info = DataConnectionInfo(
            data_connection_id="dc-123",
            tables_info=[table_info],
        )
        semantic_model = await generator.generate_semantic_data_model(
            name="Test Model",
            description="Test",
            data_connections_info=[data_connection_info],
            files_info=[],
        )
        result = _get_data_connection_table_names(semantic_model)
        assert result == {"dc_table"}

    @pytest.mark.asyncio
    async def test_excludes_file_reference_tables(self):
        """Should not include tables with file_reference but no data_connection_id."""
        from agent_platform.core.payloads.semantic_data_model_payloads import (
            ColumnInfo,
            FileInfo,
            TableInfo,
        )
        from agent_platform.server.kernel.semantic_data_model_generator import (
            SemanticDataModelGenerator,
        )
        from agent_platform.server.semantic_data_models.enhancer.prompts import (
            _get_data_connection_table_names,
        )

        generator = SemanticDataModelGenerator()
        # Physical column from Excel header (whitespace/special chars)
        column_info = ColumnInfo(name="Revenue ($)", data_type="TEXT", sample_values=["100", "200"])
        # Physical table name from Excel sheet (whitespace/special chars)
        table_info = TableInfo(
            name="Q1 Sales Report!",
            database="test_db",
            schema="public",
            columns=[column_info],
        )
        file_info = FileInfo(
            thread_id="t-123",
            file_ref="quarterly_report.xlsx",
            tables_info=[table_info],
            sheet_name="Q1 Sales Report!",
        )
        semantic_model = await generator.generate_semantic_data_model(
            name="Test Model",
            description="Test",
            data_connections_info=[],
            files_info=[file_info],
        )
        result = _get_data_connection_table_names(semantic_model)
        assert result == set()

    @pytest.mark.asyncio
    async def test_mixed_tables(self):
        """Should only return data connection table names in mixed model."""
        from agent_platform.core.payloads.semantic_data_model_payloads import (
            ColumnInfo,
            DataConnectionInfo,
            FileInfo,
            TableInfo,
        )
        from agent_platform.server.kernel.semantic_data_model_generator import (
            SemanticDataModelGenerator,
        )
        from agent_platform.server.semantic_data_models.enhancer.prompts import (
            _get_data_connection_table_names,
        )

        generator = SemanticDataModelGenerator()
        # Physical column for DC tables (abbreviated)
        dc_col = ColumnInfo(name="cust_id", data_type="TEXT", sample_values=["1"])
        # Physical column for file table (from header with whitespace)
        file_col = ColumnInfo(name="Order Total ($)", data_type="TEXT", sample_values=["100"])

        # Data connection tables with abbreviated physical names
        dc_table_1 = TableInfo(name="cust_tbl", database="db", schema="public", columns=[dc_col])
        dc_table_2 = TableInfo(name="ord_tbl", database="db", schema="public", columns=[dc_col])
        data_connection_info_1 = DataConnectionInfo(data_connection_id="dc-1", tables_info=[dc_table_1])
        data_connection_info_2 = DataConnectionInfo(data_connection_id="dc-2", tables_info=[dc_table_2])

        # File table with sheet name (whitespace/special chars)
        file_table = TableInfo(name="Orders & Returns 2024", database="db", schema="public", columns=[file_col])
        file_info = FileInfo(
            thread_id="t-123",
            file_ref="orders.xlsx",
            tables_info=[file_table],
            sheet_name="Orders & Returns 2024",
        )

        semantic_model = await generator.generate_semantic_data_model(
            name="Test Model",
            description="Test",
            data_connections_info=[data_connection_info_1, data_connection_info_2],
            files_info=[file_info],
        )
        result = _get_data_connection_table_names(semantic_model)
        assert result == {"cust_tbl", "ord_tbl"}

    @pytest.mark.asyncio
    async def test_empty_tables(self):
        """Should return empty set for model with no tables."""
        from agent_platform.server.kernel.semantic_data_model_generator import (
            SemanticDataModelGenerator,
        )
        from agent_platform.server.semantic_data_models.enhancer.prompts import (
            _get_data_connection_table_names,
        )

        generator = SemanticDataModelGenerator()
        semantic_model = await generator.generate_semantic_data_model(
            name="Test Model",
            description="Test",
            data_connections_info=[],
            files_info=[],
        )
        result = _get_data_connection_table_names(semantic_model)
        assert result == set()


class TestResetLogicalNamesToPhysicalForDataConnections:
    """Tests for reset_logical_names_to_physical_for_data_connections function."""

    @pytest.mark.asyncio
    async def test_resets_table_name_to_physical_for_data_connection(self):
        """Table name should be reset to base_table.table for data connection tables."""
        from agent_platform.core.payloads.semantic_data_model_payloads import (
            ColumnInfo,
            DataConnectionInfo,
            TableInfo,
        )
        from agent_platform.server.kernel.semantic_data_model_generator import (
            SemanticDataModelGenerator,
        )
        from agent_platform.server.semantic_data_models.enhancer.enhancer import (
            reset_logical_names_to_physical_for_data_connections,
        )

        generator = SemanticDataModelGenerator()
        # Physical column name (abbreviated, as typically found in databases)
        column_info = ColumnInfo(name="col1", data_type="TEXT", sample_values=["a", "b"])
        # Physical table name (abbreviated) - this becomes base_table.table
        table_info = TableInfo(
            name="sd_raw_tbl",  # Physical table name
            database="test_db",
            schema="public",
            columns=[column_info],
        )
        data_connection_info = DataConnectionInfo(
            data_connection_id="dc-123",
            tables_info=[table_info],
        )
        semantic_model = await generator.generate_semantic_data_model(
            name="Test Model",
            description="Test",
            data_connections_info=[data_connection_info],
            files_info=[],
        )
        # After generation: LogicalTable.name = base_table.table = "sd_raw_tbl"
        # Simulate LLM changing the logical name to a friendly name
        semantic_model["tables"][0]["name"] = "sales_data_table"  # type: ignore[index]

        # Reset should restore logical name to match physical name (base_table.table)
        reset_logical_names_to_physical_for_data_connections(semantic_model)
        assert semantic_model["tables"][0]["name"] == "sd_raw_tbl"  # type: ignore[index]

    @pytest.mark.asyncio
    async def test_resets_column_names_for_dimensions_facts_time_dimensions(self):
        """Column names should be reset to expr for dimensions, facts, time_dimensions."""
        from agent_platform.core.payloads.semantic_data_model_payloads import (
            ColumnInfo,
            DataConnectionInfo,
            TableInfo,
        )
        from agent_platform.server.kernel.semantic_data_model_generator import (
            SemanticDataModelGenerator,
        )
        from agent_platform.server.semantic_data_models.enhancer.enhancer import (
            reset_logical_names_to_physical_for_data_connections,
        )

        generator = SemanticDataModelGenerator()
        # Physical column names (abbreviated, as in real databases)
        # These become both Dimension.name and Dimension.expr after generation
        # Dimension: name containing "name" or ending with "_id" -> becomes dimension
        dim_col = ColumnInfo(name="cust_id", data_type="TEXT", sample_values=["C001", "C002"])
        # Fact: numeric type (DECIMAL is in numeric_types) -> becomes fact
        fact_col = ColumnInfo(name="rev_amt", data_type="DECIMAL", sample_values=["100.50"])
        # Time dimension: timestamp type -> becomes time_dimension
        time_col = ColumnInfo(name="ord_dt", data_type="TIMESTAMP", sample_values=["2024-01-01"])
        table_info = TableInfo(
            name="sales_tbl",
            database="test_db",
            schema="public",
            columns=[dim_col, fact_col, time_col],
        )
        data_connection_info = DataConnectionInfo(
            data_connection_id="dc-123",
            tables_info=[table_info],
        )
        semantic_model = await generator.generate_semantic_data_model(
            name="Test Model",
            description="Test",
            data_connections_info=[data_connection_info],
            files_info=[],
        )

        # After generation: column.name = column.expr = physical name
        # Simulate LLM changing logical column names to friendly names
        table = semantic_model["tables"][0]  # type: ignore[index]
        dimensions = table.get("dimensions")
        facts = table.get("facts")
        time_dims = table.get("time_dimensions")
        assert dimensions is not None
        assert facts is not None
        assert time_dims is not None
        dimensions[0]["name"] = "customer_name"  # Friendly logical name
        facts[0]["name"] = "revenue_amount"  # Friendly logical name
        time_dims[0]["name"] = "order_date"  # Friendly logical name

        # Reset should restore logical names to match expr (physical column names)
        reset_logical_names_to_physical_for_data_connections(semantic_model)

        assert dimensions[0]["name"] == "cust_id"  # Back to physical
        assert facts[0]["name"] == "rev_amt"  # Back to physical
        assert time_dims[0]["name"] == "ord_dt"  # Back to physical

    @pytest.mark.asyncio
    async def test_preserves_metric_names(self):
        """Metric names should NOT be reset since expr can be complex SQL expressions."""
        from agent_platform.core.payloads.semantic_data_model_payloads import (
            ColumnInfo,
            DataConnectionInfo,
            TableInfo,
        )
        from agent_platform.server.kernel.semantic_data_model_generator import (
            SemanticDataModelGenerator,
        )
        from agent_platform.server.semantic_data_models.enhancer.enhancer import (
            reset_logical_names_to_physical_for_data_connections,
        )

        generator = SemanticDataModelGenerator()
        column_info = ColumnInfo(name="col1", data_type="TEXT", sample_values=["a"])
        table_info = TableInfo(
            name="phys_table",
            database="test_db",
            schema="public",
            columns=[column_info],
        )
        data_connection_info = DataConnectionInfo(
            data_connection_id="dc-123",
            tables_info=[table_info],
        )
        semantic_model = await generator.generate_semantic_data_model(
            name="Test Model",
            description="Test",
            data_connections_info=[data_connection_info],
            files_info=[],
        )

        # Manually add a metric (generator doesn't create metrics automatically)
        table = semantic_model["tables"][0]  # type: ignore[index]
        table["metrics"] = [
            {
                "name": "Total_Energy",  # LLM-generated friendly name
                "expr": "SUM(oil) + (SUM(gas) / 6.0)",  # Complex expression
            }
        ]

        reset_logical_names_to_physical_for_data_connections(semantic_model)

        # Metric name should be preserved (not reset to expr)
        assert table["metrics"][0]["name"] == "Total_Energy"

    @pytest.mark.asyncio
    async def test_skips_tables_without_data_connection_id(self):
        """Tables without data_connection_id should not be modified."""
        from agent_platform.core.payloads.semantic_data_model_payloads import (
            ColumnInfo,
            FileInfo,
            TableInfo,
        )
        from agent_platform.server.kernel.semantic_data_model_generator import (
            SemanticDataModelGenerator,
        )
        from agent_platform.server.semantic_data_models.enhancer.enhancer import (
            reset_logical_names_to_physical_for_data_connections,
        )

        generator = SemanticDataModelGenerator()
        # Physical column name from Excel header row (has whitespace/special chars)
        column_info = ColumnInfo(name="Customer Name (Primary)", data_type="TEXT", sample_values=["Alice"])
        # Physical table name from Excel sheet name (has whitespace/special chars)
        table_info = TableInfo(
            name="Sales Data Q1 2024!",
            database="test_db",
            schema="public",
            columns=[column_info],
        )
        file_info = FileInfo(
            thread_id="t-123",
            file_ref="sales_report.xlsx",
            tables_info=[table_info],
            sheet_name="Sales Data Q1 2024!",
        )
        semantic_model = await generator.generate_semantic_data_model(
            name="Test Model",
            description="Test",
            data_connections_info=[],
            files_info=[file_info],
        )

        # LLM generates clean database-style logical names
        table = semantic_model["tables"][0]  # type: ignore[index]
        table["name"] = "sales_data_q1_2024"  # Clean logical table name
        dimensions = table.get("dimensions")
        assert dimensions is not None
        dimensions[0]["name"] = "customer_name"  # Clean logical column name

        reset_logical_names_to_physical_for_data_connections(semantic_model)

        # File table should NOT be modified - clean logical names should persist
        assert table["name"] == "sales_data_q1_2024"
        assert dimensions[0]["name"] == "customer_name"

    @pytest.mark.asyncio
    async def test_only_modifies_data_connection_tables_in_mixed_model(self):
        """Only tables with data_connection_id should be modified."""
        from agent_platform.core.payloads.semantic_data_model_payloads import (
            ColumnInfo,
            DataConnectionInfo,
            FileInfo,
            TableInfo,
        )
        from agent_platform.server.kernel.semantic_data_model_generator import (
            SemanticDataModelGenerator,
        )
        from agent_platform.server.semantic_data_models.enhancer.enhancer import (
            reset_logical_names_to_physical_for_data_connections,
        )

        generator = SemanticDataModelGenerator()
        # Physical column name (abbreviated) for data connection table
        dc_col = ColumnInfo(name="cust_nm", data_type="TEXT", sample_values=["Alice"])
        # Physical column name from Excel header (has whitespace/special chars)
        file_col = ColumnInfo(name="Product Name ($)", data_type="TEXT", sample_values=["Widget"])

        # Data connection table with abbreviated physical name
        dc_table = TableInfo(name="dc_raw_tbl", database="db", schema="public", columns=[dc_col])
        data_connection_info = DataConnectionInfo(data_connection_id="dc-123", tables_info=[dc_table])

        # File table with sheet name as physical name (whitespace/special chars)
        file_table = TableInfo(name="Products & Inventory!", database="db", schema="public", columns=[file_col])
        file_info = FileInfo(
            thread_id="t-123",
            file_ref="inventory.xlsx",
            tables_info=[file_table],
            sheet_name="Products & Inventory!",
        )

        semantic_model = await generator.generate_semantic_data_model(
            name="Test Model",
            description="Test",
            data_connections_info=[data_connection_info],
            files_info=[file_info],
        )

        # LLM generates friendly names for DC table, clean DB-style for file table
        dc_tbl = semantic_model["tables"][0]  # type: ignore[index]
        dc_tbl["name"] = "CustomerData"  # Friendly logical name
        dc_dims = dc_tbl.get("dimensions")
        assert dc_dims is not None
        dc_dims[0]["name"] = "CustomerName"  # Friendly logical name

        file_tbl = semantic_model["tables"][1]  # type: ignore[index]
        file_tbl["name"] = "products_inventory"  # Clean DB-style logical name
        file_dims = file_tbl.get("dimensions")
        assert file_dims is not None
        file_dims[0]["name"] = "product_name"  # Clean DB-style logical name

        reset_logical_names_to_physical_for_data_connections(semantic_model)

        # Data connection table should be reset to physical names
        assert dc_tbl["name"] == "dc_raw_tbl"
        assert dc_dims[0]["name"] == "cust_nm"
        # File table should NOT be modified - keeps clean logical names
        assert file_tbl["name"] == "products_inventory"
        assert file_dims[0]["name"] == "product_name"

    @pytest.mark.asyncio
    async def test_handles_missing_column_categories(self):
        """Should handle tables with missing column categories."""
        from agent_platform.core.payloads.semantic_data_model_payloads import (
            DataConnectionInfo,
            TableInfo,
        )
        from agent_platform.server.kernel.semantic_data_model_generator import (
            SemanticDataModelGenerator,
        )
        from agent_platform.server.semantic_data_models.enhancer.enhancer import (
            reset_logical_names_to_physical_for_data_connections,
        )

        generator = SemanticDataModelGenerator()
        # Table with no columns (physical name is abbreviated)
        table_info = TableInfo(
            name="empty_tbl",  # Physical table name
            database="test_db",
            schema="public",
            columns=[],
        )
        data_connection_info = DataConnectionInfo(
            data_connection_id="dc-123",
            tables_info=[table_info],
        )
        semantic_model = await generator.generate_semantic_data_model(
            name="Test Model",
            description="Test",
            data_connections_info=[data_connection_info],
            files_info=[],
        )

        # Simulate LLM-generated friendly table name
        semantic_model["tables"][0]["name"] = "Empty Data Table"  # type: ignore[index]

        reset_logical_names_to_physical_for_data_connections(semantic_model)
        # Should reset to physical name
        assert semantic_model["tables"][0]["name"] == "empty_tbl"  # type: ignore[index]
