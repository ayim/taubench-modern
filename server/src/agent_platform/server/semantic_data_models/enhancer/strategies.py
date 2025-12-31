"""Enhancement strategy classes for semantic data model enhancement.

This module provides a lightweight strategy pattern for handling different modes of
semantic data model enhancement (full, tables-only, columns-only). Each enhancer
encapsulates the mode-specific logic for tool selection, response parsing, and
enhancement application.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel
    from agent_platform.core.responses.response import ResponseMessage
    from agent_platform.core.tools.tool_definition import ToolDefinition
    from agent_platform.server.semantic_data_models.enhancer.type_defs import (
        EnhancementMode,
        LLMOutputSchemas,
    )

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class BaseStrategy(ABC):
    """Base class for semantic data model enhancement strategies.

    Each enhancer encapsulates the mode-specific behavior for:
    - Tool definition selection
    - Response parsing
    - Enhancement application to the semantic model
    """

    def __init__(
        self,
        semantic_model: SemanticDataModel,
        tables_to_enhance: set[str] | None = None,
        table_to_columns_to_enhance: dict[str, list[str]] | None = None,
    ):
        """Initialize the enhancer.

        Args:
            semantic_model: The semantic data model to enhance.
            tables_to_enhance: Optional set of table names to enhance.
            table_to_columns_to_enhance: Optional mapping of table names to column names to enhance.
        """
        self.semantic_model = semantic_model
        self.tables_to_enhance = tables_to_enhance
        self.table_to_columns_to_enhance = table_to_columns_to_enhance

    @property
    @abstractmethod
    def mode(self) -> EnhancementMode:
        """Return the enhancement mode for this enhancer."""

    @property
    @abstractmethod
    def tool(self) -> ToolDefinition:
        """Return the tool definition for this enhancement mode."""

    @abstractmethod
    def parse_response(self, response: ResponseMessage) -> LLMOutputSchemas:
        """Parse and validate the LLM response for this enhancement mode.

        Args:
            response: The response message from the LLM.

        Returns:
            The parsed result specific to this enhancement mode.

        Raises:
            LLMResponseError: If the response cannot be parsed or validated.
        """

    @abstractmethod
    def apply_enhancement(self, parsed_result: LLMOutputSchemas) -> None:
        """Apply the parsed enhancement result to the semantic model.

        Args:
            parsed_result: The parsed result from parse_response().

        Note:
            This method modifies self.semantic_model in place.
        """


class FullStrategy(BaseStrategy):
    """Enhancer for full semantic data model enhancement.

    Enhances both table metadata and columns for the entire semantic model or
    specified tables.
    """

    @property
    def mode(self) -> EnhancementMode:
        return "full"

    @property
    def tool(self) -> ToolDefinition:
        from agent_platform.server.semantic_data_models.enhancer.type_defs import (
            create_semantic_data_model_enhancement_tool,
        )

        return create_semantic_data_model_enhancement_tool()

    def parse_response(self, response: ResponseMessage) -> LLMOutputSchemas:
        from agent_platform.server.semantic_data_models.enhancer.parse import (
            validate_and_parse_llm_response,
        )

        return validate_and_parse_llm_response(response, mode="full")

    def apply_enhancement(self, parsed_result: LLMOutputSchemas) -> None:
        from agent_platform.server.semantic_data_models.enhancer.parse import (
            update_semantic_data_model_with_semantic_data_model_from_llm,
        )
        from agent_platform.server.semantic_data_models.enhancer.type_defs import (
            SemanticDataModelForLLM,
        )

        assert isinstance(parsed_result, SemanticDataModelForLLM)
        update_semantic_data_model_with_semantic_data_model_from_llm(
            self.semantic_model,
            parsed_result,
            self.tables_to_enhance,
            self.table_to_columns_to_enhance,
        )


class TablesOnlyStrategy(BaseStrategy):
    """Enhancer for table metadata enhancement only.

    Enhances only table-level metadata (name, description, synonyms) without
    modifying columns.
    """

    def __init__(
        self,
        semantic_model: SemanticDataModel,
        tables_to_enhance: set[str] | None = None,
        table_to_columns_to_enhance: dict[str, list[str]] | None = None,
    ):
        """Initialize the tables-only enhancer.

        Args:
            semantic_model: The semantic data model to enhance.
            tables_to_enhance: Set of table names to enhance. Should be provided
                for partial enhancement.
            table_to_columns_to_enhance: Ignored for this enhancer, but accepted
                to maintain consistent interface.
        """
        super().__init__(semantic_model, tables_to_enhance, table_to_columns_to_enhance)

    @property
    def mode(self) -> EnhancementMode:
        return "tables"

    @property
    def tool(self) -> ToolDefinition:
        from agent_platform.server.semantic_data_models.enhancer.type_defs import (
            create_tables_enhancement_tool,
        )

        return create_tables_enhancement_tool()

    def parse_response(self, response: ResponseMessage) -> LLMOutputSchemas:
        from agent_platform.server.semantic_data_models.enhancer.parse import (
            validate_and_parse_llm_response,
        )

        return validate_and_parse_llm_response(response, mode="tables")

    def apply_enhancement(self, parsed_result: LLMOutputSchemas) -> None:
        from agent_platform.server.semantic_data_models.enhancer.parse import (
            update_tables_metadata_in_semantic_model,
        )
        from agent_platform.server.semantic_data_models.enhancer.type_defs import (
            TablesOutputSchema,
        )

        assert isinstance(parsed_result, TablesOutputSchema)
        update_tables_metadata_in_semantic_model(
            self.semantic_model,
            parsed_result,
            self.tables_to_enhance,
        )


class ColumnsOnlyStrategy(BaseStrategy):
    """Enhancer for column enhancement only.

    Enhances only columns (name, description, synonyms, categorization) without
    modifying table-level metadata.
    """

    def __init__(
        self,
        semantic_model: SemanticDataModel,
        tables_to_enhance: set[str] | None = None,
        table_to_columns_to_enhance: dict[str, list[str]] | None = None,
    ):
        """Initialize the columns-only enhancer.

        Args:
            semantic_model: The semantic data model to enhance.
            tables_to_enhance: Ignored for this enhancer, but accepted to maintain
                consistent interface.
            table_to_columns_to_enhance: Mapping of table names to column names to enhance.
                Should be provided for partial enhancement.
        """
        super().__init__(semantic_model, tables_to_enhance, table_to_columns_to_enhance)

    @property
    def mode(self) -> EnhancementMode:
        return "columns"

    @property
    def tool(self) -> ToolDefinition:
        from agent_platform.server.semantic_data_models.enhancer.type_defs import (
            create_columns_enhancement_tool,
        )

        return create_columns_enhancement_tool()

    def parse_response(self, response: ResponseMessage) -> LLMOutputSchemas:
        from agent_platform.server.semantic_data_models.enhancer.parse import (
            validate_and_parse_llm_response,
        )

        return validate_and_parse_llm_response(response, mode="columns")

    def apply_enhancement(self, parsed_result: LLMOutputSchemas) -> None:
        from agent_platform.server.semantic_data_models.enhancer.parse import (
            update_columns_in_semantic_model,
        )
        from agent_platform.server.semantic_data_models.enhancer.type_defs import (
            TableToColumnsOutputSchema,
        )

        assert isinstance(parsed_result, TableToColumnsOutputSchema)
        update_columns_in_semantic_model(
            self.semantic_model,
            parsed_result,
            self.tables_to_enhance,
            self.table_to_columns_to_enhance,
        )


def create_strategy(
    semantic_model: SemanticDataModel,
    tables_to_enhance: set[str] | None = None,
    table_to_columns_to_enhance: dict[str, list[str]] | None = None,
) -> BaseStrategy:
    """Factory function to create the appropriate strategy based on parameters.

    The strategy type is determined by which parameters are provided:
    - If both tables_to_enhance and table_to_columns_to_enhance are provided: FullStrategy
    - If only tables_to_enhance is provided: TablesOnlyStrategy
    - If only table_to_columns_to_enhance is provided: ColumnsOnlyStrategy
    - If neither is provided: FullStrategy (full model enhancement)

    Args:
        semantic_model: The semantic data model to enhance.
        tables_to_enhance: Optional set of table names to enhance.
        table_to_columns_to_enhance: Optional mapping of table names to column names to enhance.

    Returns:
        An instance of the appropriate strategy subclass.
    """
    if tables_to_enhance and table_to_columns_to_enhance:
        # Both provided - enhance full model for specified elements
        logger.info("Creating FullStrategy (tables and columns specified)")
        return FullStrategy(
            semantic_model,
            tables_to_enhance=tables_to_enhance,
            table_to_columns_to_enhance=table_to_columns_to_enhance,
        )
    elif tables_to_enhance:
        # Only tables specified - enhance table metadata only
        logger.info("Creating TablesOnlyStrategy")
        return TablesOnlyStrategy(
            semantic_model,
            tables_to_enhance=tables_to_enhance,
        )
    elif table_to_columns_to_enhance:
        # Only columns specified - enhance columns only
        logger.info("Creating ColumnsOnlyStrategy")
        return ColumnsOnlyStrategy(
            semantic_model,
            table_to_columns_to_enhance=table_to_columns_to_enhance,
        )
    else:
        # Nothing specified - enhance full model
        logger.info("Creating FullStrategy (full model enhancement)")
        return FullStrategy(semantic_model)
