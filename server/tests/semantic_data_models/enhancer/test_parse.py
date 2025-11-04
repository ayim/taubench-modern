"""Unit tests for parse.py functions in the semantic data model enhancer."""

from __future__ import annotations

import json

import pytest

from agent_platform.core.data_frames.semantic_data_model_types import (
    BaseTable,
    Dimension,
    Fact,
    LogicalTable,
    SemanticDataModel,
    TimeDimension,
)
from agent_platform.core.responses.response import ResponseMessage


def _create_tool_response_message(tool_input: dict) -> ResponseMessage:
    """Helper to create a ResponseMessage with tool call content."""
    from agent_platform.core.responses.content.tool_use import ResponseToolUseContent

    return ResponseMessage(
        role="agent",
        content=[
            ResponseToolUseContent(
                tool_call_id="test_call_id",
                tool_name="enhance_semantic_data_model",
                tool_input_raw=json.dumps(tool_input),
            )
        ],
    )


def _create_empty_response_message() -> ResponseMessage:
    """Helper to create a ResponseMessage with no content."""
    return ResponseMessage(
        role="agent",
        content=[],
    )


@pytest.fixture
def example_semantic_model() -> SemanticDataModel:
    """Create an example semantic model for testing."""
    dimension: Dimension = {
        "name": "product_category",
        "synonyms": ["item_category"],
        "description": "The category of the product.",
        "expr": "cat",
        "data_type": "NUMBER",
        "unique": False,
    }

    fact: Fact = {
        "name": "revenue",
        "description": "Total revenue",
        "expr": "rev",
        "data_type": "NUMERIC",
    }

    time_dimension: TimeDimension = {
        "name": "sale_date",
        "description": "The date of sale",
        "expr": "sale_dt",
        "data_type": "DATE",
        "unique": False,
    }

    base_table: BaseTable = {
        "database": "public",  # Match what the code expects (uses schema as database)
        "schema": "public",
        "table": "sales_data",
    }

    table: LogicalTable = {
        "name": "sales_table",
        "description": "Sales data table",
        "base_table": base_table,
        "dimensions": [dimension],
        "facts": [fact],
        "time_dimensions": [time_dimension],
        "filters": [],
    }

    return {
        "name": "Sales Model",
        "description": "A test semantic model",
        "tables": [table],
    }


class TestValidateAndParseLLMResponse:
    """Tests for validate_and_parse_llm_response function."""

    def test_validate_and_parse_schema_validation_error(self):
        """Verify SchemaValidationError when tool input doesn't match Pydantic schema."""
        from agent_platform.server.semantic_data_models.enhancer.errors import (
            SchemaValidationError,
        )
        from agent_platform.server.semantic_data_models.enhancer.parse import (
            validate_and_parse_llm_response,
        )

        # Invalid schema - missing required "name" field
        invalid_tool_input = {"tables": []}
        response = _create_tool_response_message(invalid_tool_input)

        with pytest.raises(SchemaValidationError) as exc_info:
            validate_and_parse_llm_response(response, mode="full")

        assert "schema" in exc_info.value.improvement_request.lower()
        assert exc_info.value.response_message == response

    def test_validate_and_parse_success_full_mode(self):
        """Verify successful parsing returns SemanticDataModelForLLM."""
        from agent_platform.server.semantic_data_models.enhancer.parse import (
            validate_and_parse_llm_response,
        )
        from agent_platform.server.semantic_data_models.enhancer.type_defs import (
            SemanticDataModelForLLM,
        )

        valid_tool_input = {
            "name": "Test Model",
            "description": "A test model",
            "tables": [
                {
                    "name": "test_table",
                    "base_table": {"schema": "public", "table": "sales_data"},
                    "columns": [],
                }
            ],
        }
        response = _create_tool_response_message(valid_tool_input)

        result = validate_and_parse_llm_response(response, mode="full")
        assert isinstance(result, SemanticDataModelForLLM)
        assert result.name == "Test Model"

    def test_validate_and_parse_success_tables_mode(self):
        """Verify successful parsing returns TablesOutputSchema."""
        from agent_platform.server.semantic_data_models.enhancer.parse import (
            validate_and_parse_llm_response,
        )
        from agent_platform.server.semantic_data_models.enhancer.type_defs import (
            TablesOutputSchema,
        )

        valid_tool_input = {
            "tables": [
                {
                    "name": "test_table",
                    "base_table": {"schema": "public", "table": "sales_data"},
                }
            ]
        }
        response = _create_tool_response_message(valid_tool_input)

        result = validate_and_parse_llm_response(response, mode="tables")
        assert isinstance(result, TablesOutputSchema)
        assert len(result.tables) == 1

    def test_validate_and_parse_success_columns_mode(self):
        """Verify successful parsing returns TableToColumnsOutputSchema."""
        from agent_platform.server.semantic_data_models.enhancer.parse import (
            validate_and_parse_llm_response,
        )
        from agent_platform.server.semantic_data_models.enhancer.type_defs import (
            TableToColumnsOutputSchema,
        )

        valid_tool_input = {
            "table_to_columns": {
                "test_table": [
                    {
                        "name": "test_column",
                        "expr": "col",
                        "category": "dimension",
                    }
                ]
            }
        }
        response = _create_tool_response_message(valid_tool_input)

        result = validate_and_parse_llm_response(response, mode="columns")
        assert isinstance(result, TableToColumnsOutputSchema)
        assert "test_table" in result.table_to_columns


class TestUpdateTableColumns:
    """Tests for _update_table_columns function."""

    def test_update_table_columns_moves_dimension_to_fact(self, example_semantic_model):
        """Verify column moves from dimensions to facts when category changes."""
        from agent_platform.server.semantic_data_models.enhancer.parse import (
            update_semantic_data_model_with_semantic_data_model_from_llm,
        )
        from agent_platform.server.semantic_data_models.enhancer.type_defs import (
            BaseTable,
            ColumnForLLM,
            LogicalTable,
            SemanticDataModelForLLM,
        )

        # Create LLM model with changed category
        table = example_semantic_model["tables"][0]
        original_dimension = table["dimensions"][0]

        llm_column = ColumnForLLM(
            name=original_dimension["name"],
            expr=original_dimension["expr"],
            category="fact",  # Changed from dimension to fact
            description="Updated description",
            synonyms=["new_synonym"],
        )

        llm_table = LogicalTable(
            name=table["name"],
            base_table=BaseTable(
                schema=table["base_table"]["schema"],
                table=table["base_table"]["table"],
            ),
            columns=[llm_column],
        )

        llm_model = SemanticDataModelForLLM(
            name=example_semantic_model["name"],
            description=example_semantic_model["description"],
            tables=[llm_table],
        )

        # Update the semantic model
        update_semantic_data_model_with_semantic_data_model_from_llm(
            example_semantic_model,
            llm_model,
        )

        # Verify column moved from dimensions to facts
        updated_table = example_semantic_model["tables"][0]
        assert len(updated_table.get("dimensions", [])) == 0
        # Should have original fact plus the moved dimension
        facts = updated_table.get("facts", [])
        assert len(facts) == 2  # Original fact + moved dimension
        # Find the moved column by expr
        moved_fact = next(f for f in facts if f["expr"] == original_dimension["expr"])
        assert moved_fact["description"] == "Updated description"
        assert moved_fact["synonyms"] == ["new_synonym"]

    def test_update_table_columns_respects_column_filtering(self, example_semantic_model):
        """Verify only specified columns are updated when table_to_columns_to_enhance is provided."""  # noqa: E501
        from agent_platform.server.semantic_data_models.enhancer.parse import (
            update_semantic_data_model_with_semantic_data_model_from_llm,
        )
        from agent_platform.server.semantic_data_models.enhancer.type_defs import (
            BaseTable,
            ColumnForLLM,
            LogicalTable,
            SemanticDataModelForLLM,
        )

        table = example_semantic_model["tables"][0]
        original_dimension = table["dimensions"][0]

        # Create LLM columns - one should be filtered out
        llm_column1 = ColumnForLLM(
            name=original_dimension["name"],
            expr=original_dimension["expr"],
            category="dimension",
            description="Updated description",
        )

        llm_column2 = ColumnForLLM(
            name=table["facts"][0]["name"],
            expr=table["facts"][0]["expr"],
            category="fact",
            description="Updated fact description",
        )

        llm_table = LogicalTable(
            name=table["name"],
            base_table=BaseTable(
                schema=table["base_table"]["schema"],
                table=table["base_table"]["table"],
            ),
            columns=[llm_column1, llm_column2],
        )

        llm_model = SemanticDataModelForLLM(
            name=example_semantic_model["name"],
            description=example_semantic_model["description"],
            tables=[llm_table],
        )

        # Update with filtering - use EXPR not NAME (critical bug fix)
        update_semantic_data_model_with_semantic_data_model_from_llm(
            example_semantic_model,
            llm_model,
            table_to_columns_to_enhance={table["name"]: [original_dimension["expr"]]},
        )

        # Verify only first column was updated
        updated_table = example_semantic_model["tables"][0]
        assert updated_table["dimensions"][0]["description"] == "Updated description"
        # Second column (fact) should not be updated
        assert updated_table["facts"][0]["description"] != "Updated fact description"

    def test_update_table_columns_filtering_uses_expr_not_name(self, example_semantic_model):
        """REGRESSION TEST: Verify filtering checks expr (not name) - Bug fix for lost descriptions."""  # noqa: E501
        from agent_platform.server.semantic_data_models.enhancer.parse import (
            update_semantic_data_model_with_semantic_data_model_from_llm,
        )
        from agent_platform.server.semantic_data_models.enhancer.type_defs import (
            BaseTable,
            ColumnForLLM,
            LogicalTable,
            SemanticDataModelForLLM,
        )

        table = example_semantic_model["tables"][0]
        original_dimension = table["dimensions"][0]

        # LLM changes the logical name but expr stays the same (stable identifier)
        llm_column = ColumnForLLM(
            name="new_enhanced_name",  # Changed logical name
            expr=original_dimension["expr"],  # Same expr (stable identifier)
            category="dimension",
            description="New enhanced description",
            synonyms=["enhanced_synonym"],
        )

        llm_table = LogicalTable(
            name=table["name"],
            base_table=BaseTable(
                schema=table["base_table"]["schema"],
                table=table["base_table"]["table"],
            ),
            columns=[llm_column],
        )

        llm_model = SemanticDataModelForLLM(
            name=example_semantic_model["name"],
            description=example_semantic_model["description"],
            tables=[llm_table],
        )

        # Filter uses expr (the stable identifier)
        # This should match and update the column even though name changed
        update_semantic_data_model_with_semantic_data_model_from_llm(
            example_semantic_model,
            llm_model,
            table_to_columns_to_enhance={table["name"]: [original_dimension["expr"]]},
        )

        # Verify column was updated despite name change
        updated_table = example_semantic_model["tables"][0]
        updated_column = updated_table["dimensions"][0]
        assert updated_column["description"] == "New enhanced description"
        assert updated_column["synonyms"] == ["enhanced_synonym"]
        assert updated_column["name"] == "new_enhanced_name"  # Name also updated

    def test_update_table_columns_updates_synonyms_and_description(self, example_semantic_model):
        """Verify synonyms and descriptions are properly updated."""
        from agent_platform.server.semantic_data_models.enhancer.parse import (
            update_semantic_data_model_with_semantic_data_model_from_llm,
        )
        from agent_platform.server.semantic_data_models.enhancer.type_defs import (
            BaseTable,
            ColumnForLLM,
            LogicalTable,
            SemanticDataModelForLLM,
        )

        table = example_semantic_model["tables"][0]
        original_dimension = table["dimensions"][0]

        llm_column = ColumnForLLM(
            name=original_dimension["name"],
            expr=original_dimension["expr"],
            category="dimension",
            description="New description",
            synonyms=["new_synonym1", "new_synonym2"],
        )

        llm_table = LogicalTable(
            name=table["name"],
            base_table=BaseTable(
                schema=table["base_table"]["schema"],
                table=table["base_table"]["table"],
            ),
            columns=[llm_column],
        )

        llm_model = SemanticDataModelForLLM(
            name=example_semantic_model["name"],
            description=example_semantic_model["description"],
            tables=[llm_table],
        )

        update_semantic_data_model_with_semantic_data_model_from_llm(
            example_semantic_model,
            llm_model,
        )

        updated_table = example_semantic_model["tables"][0]
        assert updated_table["dimensions"][0]["description"] == "New description"
        assert updated_table["dimensions"][0]["synonyms"] == ["new_synonym1", "new_synonym2"]

    def test_update_table_columns_handles_missing_column(self, example_semantic_model):
        """Verify graceful handling when column expr not found."""
        from agent_platform.server.semantic_data_models.enhancer.parse import (
            update_semantic_data_model_with_semantic_data_model_from_llm,
        )
        from agent_platform.server.semantic_data_models.enhancer.type_defs import (
            BaseTable,
            ColumnForLLM,
            LogicalTable,
            SemanticDataModelForLLM,
        )

        table = example_semantic_model["tables"][0]

        # Create LLM column with non-existent expr
        llm_column = ColumnForLLM(
            name="non_existent",
            expr="non_existent_expr",
            category="dimension",
        )

        llm_table = LogicalTable(
            name=table["name"],
            base_table=BaseTable(
                schema=table["base_table"]["schema"],
                table=table["base_table"]["table"],
            ),
            columns=[llm_column],
        )

        llm_model = SemanticDataModelForLLM(
            name=example_semantic_model["name"],
            description=example_semantic_model["description"],
            tables=[llm_table],
        )

        # Should not raise, but should log/handle gracefully
        update_semantic_data_model_with_semantic_data_model_from_llm(
            example_semantic_model,
            llm_model,
        )

        # Original columns should remain unchanged
        updated_table = example_semantic_model["tables"][0]
        assert len(updated_table["dimensions"]) == 1  # Original dimension still there


class TestUpdateTablesMetadata:
    """Tests for update_tables_metadata_in_semantic_model function."""

    def test_update_tables_metadata_updates_correctly(self, example_semantic_model):
        """Verify table name, description, synonyms are updated."""
        from agent_platform.server.semantic_data_models.enhancer.parse import (
            update_tables_metadata_in_semantic_model,
        )
        from agent_platform.server.semantic_data_models.enhancer.type_defs import (
            BaseTable,
            LogicalTableMetadataForLLM,
            TablesOutputSchema,
        )

        table = example_semantic_model["tables"][0]

        # The code uses schema as both database and schema for matching
        # So we need to use schema="public" (not database="sales")
        enhanced_table = LogicalTableMetadataForLLM(
            name=table["name"],
            base_table=BaseTable(
                schema=table["base_table"]["schema"],  # "public"
                table=table["base_table"]["table"],
            ),
            description="Updated description",
            synonyms=["new_synonym"],
        )

        table_metadata = TablesOutputSchema(tables=[enhanced_table])

        update_tables_metadata_in_semantic_model(
            example_semantic_model,
            table_metadata,
        )

        updated_table = example_semantic_model["tables"][0]
        assert updated_table["description"] == "Updated description"
        assert updated_table["synonyms"] == ["new_synonym"]

    def test_update_tables_metadata_respects_filtering(self, example_semantic_model):
        """Verify only specified tables are updated when tables_to_enhance is provided."""
        from agent_platform.server.semantic_data_models.enhancer.parse import (
            update_tables_metadata_in_semantic_model,
        )
        from agent_platform.server.semantic_data_models.enhancer.type_defs import (
            BaseTable,
            LogicalTableMetadataForLLM,
            TablesOutputSchema,
        )

        table = example_semantic_model["tables"][0]
        original_description = table["description"]

        enhanced_table = LogicalTableMetadataForLLM(
            name=table["name"],
            base_table=BaseTable(
                schema=table["base_table"]["schema"],
                table=table["base_table"]["table"],
            ),
            description="Updated description",
        )

        table_metadata = TablesOutputSchema(tables=[enhanced_table])

        # Filter with non-matching table name
        update_tables_metadata_in_semantic_model(
            example_semantic_model,
            table_metadata,
            tables_to_enhance={"different_table"},
        )

        # Table should not be updated
        updated_table = example_semantic_model["tables"][0]
        assert updated_table["description"] == original_description

    def test_update_tables_metadata_handles_missing_table(self, example_semantic_model):
        """Verify graceful handling (logging) when table not found."""
        from agent_platform.server.semantic_data_models.enhancer.parse import (
            update_tables_metadata_in_semantic_model,
        )
        from agent_platform.server.semantic_data_models.enhancer.type_defs import (
            BaseTable,
            LogicalTableMetadataForLLM,
            TablesOutputSchema,
        )

        enhanced_table = LogicalTableMetadataForLLM(
            name="non_existent_table",
            base_table=BaseTable(
                schema="public",
                table="non_existent",
            ),
            description="Updated description",
        )

        table_metadata = TablesOutputSchema(tables=[enhanced_table])

        # Should not raise, but should log warning
        update_tables_metadata_in_semantic_model(
            example_semantic_model,
            table_metadata,
        )

        # Original table should remain unchanged
        assert len(example_semantic_model["tables"]) == 1


class TestUpdateColumnsInSemanticModel:
    """Tests for update_columns_in_semantic_model function."""

    def test_update_columns_updates_correctly(self, example_semantic_model):
        """Verify columns are correctly updated via the full flow."""
        from agent_platform.server.semantic_data_models.enhancer.parse import (
            update_columns_in_semantic_model,
        )
        from agent_platform.server.semantic_data_models.enhancer.type_defs import (
            ColumnForLLM,
            TableToColumnsOutputSchema,
        )

        table = example_semantic_model["tables"][0]
        original_dimension = table["dimensions"][0]

        enhanced_column = ColumnForLLM(
            name=original_dimension["name"],
            expr=original_dimension["expr"],
            category="dimension",
            description="Enhanced description",
            synonyms=["enhanced_synonym"],
        )

        table_to_columns = TableToColumnsOutputSchema(
            table_to_columns={
                table["name"]: [enhanced_column],
            }
        )

        update_columns_in_semantic_model(
            example_semantic_model,
            table_to_columns,
        )

        updated_table = example_semantic_model["tables"][0]
        assert updated_table["dimensions"][0]["description"] == "Enhanced description"
        assert updated_table["dimensions"][0]["synonyms"] == ["enhanced_synonym"]

    def test_update_columns_respects_filtering(self, example_semantic_model):
        """Verify filtering by table and column names."""
        from agent_platform.server.semantic_data_models.enhancer.parse import (
            update_columns_in_semantic_model,
        )
        from agent_platform.server.semantic_data_models.enhancer.type_defs import (
            ColumnForLLM,
            TableToColumnsOutputSchema,
        )

        table = example_semantic_model["tables"][0]
        original_dimension = table["dimensions"][0]
        original_fact = table["facts"][0]

        enhanced_column = ColumnForLLM(
            name=original_dimension["name"],
            expr=original_dimension["expr"],
            category="dimension",
            description="Enhanced description",
        )

        table_to_columns = TableToColumnsOutputSchema(
            table_to_columns={
                table["name"]: [enhanced_column],
            }
        )

        # Filter to only update the dimension - use EXPR not NAME (bug fix)
        update_columns_in_semantic_model(
            example_semantic_model,
            table_to_columns,
            table_to_columns_to_enhance={table["name"]: [original_dimension["expr"]]},
        )

        updated_table = example_semantic_model["tables"][0]
        assert updated_table["dimensions"][0]["description"] == "Enhanced description"
        # Fact should not be updated
        assert updated_table["facts"][0]["description"] == original_fact["description"]

    def test_update_columns_handles_missing_table(self, example_semantic_model):
        """Verify graceful handling when table not found."""
        from agent_platform.server.semantic_data_models.enhancer.parse import (
            update_columns_in_semantic_model,
        )
        from agent_platform.server.semantic_data_models.enhancer.type_defs import (
            ColumnForLLM,
            TableToColumnsOutputSchema,
        )

        enhanced_column = ColumnForLLM(
            name="test_column",
            expr="test_expr",
            category="dimension",
        )

        table_to_columns = TableToColumnsOutputSchema(
            table_to_columns={
                "non_existent_table": [enhanced_column],
            }
        )

        # Should not raise, but should log warning
        update_columns_in_semantic_model(
            example_semantic_model,
            table_to_columns,
        )

        # Original table should remain unchanged
        assert len(example_semantic_model["tables"]) == 1

    def test_update_columns_handles_missing_column(self, example_semantic_model):
        """Verify graceful handling when column not found."""
        from agent_platform.server.semantic_data_models.enhancer.parse import (
            update_columns_in_semantic_model,
        )
        from agent_platform.server.semantic_data_models.enhancer.type_defs import (
            ColumnForLLM,
            TableToColumnsOutputSchema,
        )

        table = example_semantic_model["tables"][0]

        enhanced_column = ColumnForLLM(
            name="non_existent",
            expr="non_existent_expr",
            category="dimension",
        )

        table_to_columns = TableToColumnsOutputSchema(
            table_to_columns={
                table["name"]: [enhanced_column],
            }
        )

        # Should not raise, but should log warning
        update_columns_in_semantic_model(
            example_semantic_model,
            table_to_columns,
        )

        # Original columns should remain unchanged
        updated_table = example_semantic_model["tables"][0]
        assert len(updated_table["dimensions"]) == 1  # Original dimension still there
