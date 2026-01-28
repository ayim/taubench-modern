"""Unit tests for semantic data model enhancer strategy classes."""

import pytest

from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel
from agent_platform.core.payloads.semantic_data_model_payloads import TableInfo
from agent_platform.server.kernel.semantic_data_model_generator import ColumnInfo, DataConnectionInfo


@pytest.fixture
async def semantic_model() -> SemanticDataModel:
    """Fixture to generate a semantic data model."""
    from agent_platform.server.kernel.semantic_data_model_generator import (
        SemanticDataModelGenerator,
    )

    generator = SemanticDataModelGenerator()
    column_info = ColumnInfo(
        name="system_name",
        data_type="TEXT",
        sample_values=["GPT-4", "Claude-2"],
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
    return await generator.generate_semantic_data_model(
        name="test_model",
        description="Test semantic model",
        data_connections_info=[data_connection_info],
        files_info=[],
    )


@pytest.mark.asyncio
async def test_create_strategy(semantic_model):
    """Should create FullStrategy when no filtering parameters provided."""
    from agent_platform.server.semantic_data_models.enhancer.strategies import (
        FullStrategy,
        create_strategy,
    )

    strategy = create_strategy(semantic_model)

    assert isinstance(strategy, FullStrategy)
    assert strategy.mode == "full"
    assert strategy.tables_to_enhance is None
    assert strategy.table_to_columns_to_enhance is None


@pytest.mark.asyncio
async def test_creates_full_strategy_with_both_params(semantic_model):
    """Should create FullStrategy when both tables_to_enhance and table_to_columns_to_enhance provided."""
    from agent_platform.server.semantic_data_models.enhancer.strategies import (
        FullStrategy,
        create_strategy,
    )

    tables_to_enhance = {"ai_systems"}
    table_to_columns_to_enhance = {"ai_systems": ["system_name"]}

    strategy = create_strategy(
        semantic_model,
        tables_to_enhance=tables_to_enhance,
        table_to_columns_to_enhance=table_to_columns_to_enhance,
    )

    assert isinstance(strategy, FullStrategy)
    assert strategy.mode == "full"
    assert strategy.tables_to_enhance == tables_to_enhance
    assert strategy.table_to_columns_to_enhance == table_to_columns_to_enhance


@pytest.mark.asyncio
async def test_creates_tables_only_strategy(semantic_model):
    """Should create TablesOnlyStrategy when only tables_to_enhance provided."""
    from agent_platform.server.semantic_data_models.enhancer.strategies import (
        TablesOnlyStrategy,
        create_strategy,
    )

    tables_to_enhance = {"ai_systems"}

    strategy = create_strategy(
        semantic_model,
        tables_to_enhance=tables_to_enhance,
    )

    assert isinstance(strategy, TablesOnlyStrategy)
    assert strategy.mode == "tables"
    assert strategy.tables_to_enhance == tables_to_enhance
    assert strategy.table_to_columns_to_enhance is None


@pytest.mark.asyncio
async def test_create_columns_only_strategy(semantic_model):
    """Should create ColumnsOnlyStrategy when only table_to_columns_to_enhance provided."""
    from agent_platform.server.semantic_data_models.enhancer.strategies import (
        ColumnsOnlyStrategy,
        create_strategy,
    )

    strategy = create_strategy(
        semantic_model,
        table_to_columns_to_enhance={"ai_systems": ["system_name"]},
    )

    assert isinstance(strategy, ColumnsOnlyStrategy)
    assert strategy.mode == "columns"
    assert strategy.tables_to_enhance is None
    assert strategy.table_to_columns_to_enhance == {"ai_systems": ["system_name"]}


class TestFullStrategy:
    """Tests for FullStrategy class."""

    @pytest.mark.asyncio
    async def test_tool_property_returns_full_enhancement_tool(self, semantic_model):
        """Should return the semantic data model enhancement tool."""
        from agent_platform.server.semantic_data_models.enhancer.strategies import (
            FullStrategy,
        )

        strategy = FullStrategy(semantic_model)

        assert strategy.tool.name == "enhance_semantic_data_model"
        assert "enhanced semantic data model" in strategy.tool.description.lower()

    @pytest.mark.asyncio
    async def test_parse_response_validates_full_mode(self, semantic_model):
        """Should parse response using full mode validation."""
        from agent_platform.core.responses.content.tool_use import ResponseToolUseContent
        from agent_platform.core.responses.response import ResponseMessage
        from agent_platform.server.semantic_data_models.enhancer.strategies import (
            FullStrategy,
        )

        strategy = FullStrategy(semantic_model)

        # Create a valid tool call response
        tool_input = """{
            "name": "Enhanced Model",
            "description": "Enhanced description",
            "tables": [{
                "name": "table1",
                "base_table": {"table": "table1", "schema": "public"},
                "columns": [{
                    "name": "col1",
                    "expr": "col1",
                    "data_type": "TEXT",
                    "category": "dimension"
                }]
            }]
        }"""

        response = ResponseMessage(
            role="agent",
            content=[
                ResponseToolUseContent(
                    tool_call_id="call_1",
                    tool_name="enhance_semantic_data_model",
                    tool_input_raw=tool_input,
                )
            ],
        )

        parsed_result = strategy.parse_response(response)

        from agent_platform.server.semantic_data_models.enhancer.type_defs import (
            SemanticDataModelForLLM,
        )

        assert isinstance(parsed_result, SemanticDataModelForLLM)
        assert parsed_result.name == "Enhanced Model"

    @pytest.mark.asyncio
    async def test_apply_enhancement_updates_model(self, semantic_model):
        """Should apply enhancement to the semantic model."""
        from agent_platform.server.semantic_data_models.enhancer.strategies import (
            FullStrategy,
        )
        from agent_platform.server.semantic_data_models.enhancer.type_defs import (
            BaseTable,
            ColumnForLLM,
            LogicalTable,
            SemanticDataModelForLLM,
        )

        strategy = FullStrategy(semantic_model)

        # Create an enhanced model
        enhanced_model = SemanticDataModelForLLM(
            name="Enhanced Model",
            description="Enhanced description",
            tables=[
                LogicalTable(
                    name="enhanced_table",
                    base_table=BaseTable(table="ai_systems", schema="public"),
                    columns=[
                        ColumnForLLM(
                            name="ai_system_name",
                            expr="system_name",
                            data_type="TEXT",
                            category="dimension",
                            description="Enhanced column description",
                        )
                    ],
                )
            ],
        )

        strategy.apply_enhancement(enhanced_model)

        # Check that the model was updated
        assert strategy.semantic_model.name == "Enhanced Model"
        assert strategy.semantic_model.description == "Enhanced description"
        tables = strategy.semantic_model.tables
        assert tables is not None
        assert tables[0]["name"] == "enhanced_table"
        dimensions = tables[0].get("dimensions")
        assert dimensions is not None
        assert len(dimensions) > 0
        assert dimensions[0].get("name") == "ai_system_name"
        assert dimensions[0].get("description") == "Enhanced column description"


class TestTablesOnlyStrategy:
    """Tests for TablesOnlyStrategy class."""

    @pytest.mark.asyncio
    async def test_tool_property_returns_tables_enhancement_tool(self, semantic_model):
        """Should return the tables enhancement tool."""
        from agent_platform.server.semantic_data_models.enhancer.strategies import (
            TablesOnlyStrategy,
        )

        strategy = TablesOnlyStrategy(semantic_model, tables_to_enhance={"ai_systems"})

        assert strategy.tool.name == "enhance_tables"
        assert "table metadata" in strategy.tool.description.lower()

    @pytest.mark.asyncio
    async def test_apply_enhancement_updates_only_table_metadata(self, semantic_model):
        """Should only update table metadata, not columns."""
        from agent_platform.server.semantic_data_models.enhancer.strategies import (
            TablesOnlyStrategy,
        )
        from agent_platform.server.semantic_data_models.enhancer.type_defs import (
            BaseTable,
            LogicalTableMetadataForLLM,
            TablesOutputSchema,
        )

        # Store original column name
        original_col_name = semantic_model.tables[0].get("dimensions")[0]["name"]

        strategy = TablesOnlyStrategy(semantic_model, tables_to_enhance={"ai_systems"})

        # Create enhanced table metadata
        enhanced_tables = TablesOutputSchema(
            tables=[
                LogicalTableMetadataForLLM(
                    name="ai_systems",
                    base_table=BaseTable(table="ai_systems", schema="public"),
                    description="Enhanced table description",
                    synonyms=["table_synonym"],
                )
            ]
        )

        strategy.apply_enhancement(enhanced_tables)

        # Check that table metadata was updated
        assert strategy.semantic_model.tables[0]["name"] == "ai_systems"
        assert strategy.semantic_model.tables[0].get("description") == "Enhanced table description"
        assert strategy.semantic_model.tables[0].get("synonyms") == ["table_synonym"]

        # Check that column name was NOT changed
        dimensions = strategy.semantic_model.tables[0].get("dimensions")
        assert dimensions is not None
        updated_col_name = dimensions[0].get("name")
        assert updated_col_name == original_col_name


class TestColumnsOnlyStrategy:
    """Tests for ColumnsOnlyStrategy class."""

    @pytest.mark.asyncio
    async def test_tool_property_returns_columns_enhancement_tool(self, semantic_model):
        """Should return the columns enhancement tool."""
        from agent_platform.server.semantic_data_models.enhancer.strategies import (
            ColumnsOnlyStrategy,
        )

        strategy = ColumnsOnlyStrategy(
            semantic_model,
            table_to_columns_to_enhance={"table1": ["col1"]},
        )

        tool = strategy.tool
        assert tool.name == "enhance_columns"
        assert "columns" in tool.description.lower()

    @pytest.mark.asyncio
    async def test_apply_enhancement_updates_only_columns(self, semantic_model):
        """Should only update columns, not table metadata."""
        from agent_platform.server.semantic_data_models.enhancer.strategies import (
            ColumnsOnlyStrategy,
        )
        from agent_platform.server.semantic_data_models.enhancer.type_defs import (
            ColumnForLLM,
            TableToColumnsOutputSchema,
        )

        # Store original table name and description
        original_table_name = semantic_model.tables[0]["name"]
        original_table_desc = semantic_model.tables[0].get("description")

        strategy = ColumnsOnlyStrategy(
            semantic_model,
            table_to_columns_to_enhance={"ai_systems": ["system_name"]},
        )

        # Create enhanced columns
        enhanced_columns = TableToColumnsOutputSchema(
            table_to_columns={
                "ai_systems": [
                    ColumnForLLM(
                        name="ai_system_name",
                        expr="system_name",
                        data_type="TEXT",
                        category="dimension",
                        description="Enhanced column description",
                        synonyms=["col_synonym"],
                    )
                ]
            }
        )

        strategy.apply_enhancement(enhanced_columns)

        # Check that column was updated
        dimensions = strategy.semantic_model.tables[0].get("dimensions")
        assert dimensions is not None
        assert len(dimensions) > 0
        assert dimensions[0].get("name") == "ai_system_name"
        assert dimensions[0].get("description") == "Enhanced column description"
        assert dimensions[0].get("synonyms") == ["col_synonym"]

        # Check that table metadata was NOT changed
        assert strategy.semantic_model.tables[0]["name"] == original_table_name
        assert strategy.semantic_model.tables[0].get("description") == original_table_desc
