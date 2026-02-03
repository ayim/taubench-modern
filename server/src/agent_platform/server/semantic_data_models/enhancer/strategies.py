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
    from agent_platform.core.responses.response import ResponseMessage
    from agent_platform.core.semantic_data_model.types import SemanticDataModel
    from agent_platform.core.tools.tool_definition import ToolDefinition
    from agent_platform.server.semantic_data_models.enhancer.type_defs import (
        EnhancementMode,
        LLMOutputSchemas,
        SemanticDataModelForLLM,
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

    @abstractmethod
    def user_prompt(
        self,
        current_semantic_model: SemanticDataModelForLLM,
        data_connection_tables: set[str] | None = None,
    ) -> str:
        """Generate the user prompt for this enhancement mode.

        Args:
            current_semantic_model: The current semantic data model formatted for LLM.
            data_connection_tables: Optional set of table names that are data connections.

        Returns:
            The formatted user prompt string.
        """

    @abstractmethod
    def system_prompt(
        self,
        data_connection_tables: set[str] | None = None,
    ) -> str:
        """Generate the system prompt for this enhancement mode.

        Args:
            data_connection_tables: Optional set of table names that are data connections.

        Returns:
            The formatted system prompt string.
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

    def user_prompt(
        self,
        current_semantic_model: SemanticDataModelForLLM,
        data_connection_tables: set[str] | None = None,
    ) -> str:
        """Generate the user prompt for full model enhancement."""
        import json

        from jinja2 import Template

        # Define template as a local constant (pure layout, no conditionals)
        template_str = """
{{ opening }}

**Current Semantic Data Model:**
```json
{{ semantic_model_json }}
```
{{ target_section }}
**Enhancement Requirements:**

**For the semantic model:**
   - Choose a concise, domain-specific, human-readable name (generally < 25 characters)
     that reflects what the data represents (e.g., 'Product Catalog', 'Sales Transactions',
     'Customer Database')
   - Do NOT use underscores or snake_case in the model name
   - Do NOT use generic names like 'Semantic Data Model' or 'Data Model'
   - Add/improve the description explaining the business purpose and analytical use cases

**For each table:**
{% if not data_connection_tables %}   - Improve the logical name{% endif %}
   - Add/improve the description explaining the table's purpose
   - Add/change relevant synonyms that users might use to improve discoverability
{% if data_connection_tables %}   - Data connection tables: {{ ", ".join(data_connection_tables) }}{% endif %}
**For each column:**
{% if not data_connection_tables %}   - Improve the logical name{% endif %}
   - Add/improve the description explaining what the data represents
   - Add/change relevant synonyms that users might use to improve discoverability
   - Ensure proper categorization (dimension, fact, metric, time_dimension)
     (the initial categorization should be treated as a hint)


**Output Format:**
   Use the provided tool to return your enhanced result. The tool will validate your output.


**Important:**
- Ensure all synonyms are unique across the model
- For table/column logical names: make them SQL-safe (no spaces, special characters)
- For the semantic model name: keep it human-readable (spaces allowed), generally < 25 characters, and do not use underscores
- The tool will validate your output against the expected JSON schema
""".strip()  # noqa: E501

        # Build semantic model JSON
        semantic_model_json = json.dumps(current_semantic_model.model_dump(), indent=2)

        # Build opening line
        if not self.tables_to_enhance and not self.table_to_columns_to_enhance:
            opening = "Please improve the following semantic data model by improving table and column information."
        else:
            # Build specific enhancement requests
            parts = []
            if self.tables_to_enhance:
                if len(self.tables_to_enhance) == 1:
                    table_name = next(iter(self.tables_to_enhance))
                    parts.append(f'table "{table_name}"')
                else:
                    tables_list = ", ".join(f'"{t}"' for t in sorted(self.tables_to_enhance))
                    parts.append(f"tables {tables_list}")

            if self.table_to_columns_to_enhance:
                col_parts = []
                for table_name, columns in sorted(self.table_to_columns_to_enhance.items()):
                    if len(columns) == 1:
                        col_parts.append(f'column "{columns[0]}" in table "{table_name}"')
                    else:
                        cols_list = ", ".join(f'"{c}"' for c in columns)
                        col_parts.append(f'columns {cols_list} in table "{table_name}"')
                parts.append(", ".join(col_parts))

            items_text = ", ".join(parts)
            opening = (
                f"Please improve the following specific {items_text} in the semantic data model "
                "while maintaining context."
            )

        # Build target section
        target_section = ""
        if self.tables_to_enhance or self.table_to_columns_to_enhance:
            lines = ["", "**Target Items to Enhance:**"]
            # Track which tables have columns to avoid duplication
            tables_with_columns = set(
                self.table_to_columns_to_enhance.keys() if self.table_to_columns_to_enhance else []
            )

            # First, list tables that don't have columns (standalone tables)
            if self.tables_to_enhance:
                for table_name in sorted(self.tables_to_enhance):
                    if table_name not in tables_with_columns:
                        lines.append(f"- Table: {table_name}")

            # Then, list tables with their columns grouped together
            if self.table_to_columns_to_enhance:
                for table_name, columns in sorted(self.table_to_columns_to_enhance.items()):
                    lines.append(f"- Table: {table_name}")
                    for column_name in sorted(columns):
                        lines.append(f"  - Column: {column_name}")

            target_section = "\n".join(lines)

        # Render the template
        template = Template(template_str)
        return template.render(
            opening=opening,
            semantic_model_json=semantic_model_json,
            target_section=target_section,
            data_connection_tables=sorted(data_connection_tables or []),
        )

    def system_prompt(
        self,
        data_connection_tables: set[str] | None = None,
    ) -> str:
        """Generate the system prompt for full model enhancement."""
        from jinja2 import Template

        template_str = """
You are an expert data analyst and semantic model designer.

Your task is to enhance a semantic data model by improving:

**Model-Level Information:**
   - A concise, domain-specific, and human-readable name for the semantic model
     (generally < 25 characters)
     that clearly indicates what business domain or data subject it represents.
     Do NOT use underscores or snake_case in the model name.
     Examples: 'Product Catalog', 'Sales Analytics', 'Customer Orders' (NOT generic
     names like 'Semantic Data Model')
   - An improved description that explains the business purpose and use cases

**Table Information:**
For each table:
{% if not data_connection_tables %}   - Better logical name for the table{% endif %}
   - Improved description that explains the purpose of the table
   - Synonyms that users might use to refer to this table

**Column Information:**
For each column:

{% if not data_connection_tables %}   - Better logical name for the column{% endif %}
   - Improved description that explains what the data represents
   - Synonyms that users might use to refer to this column
   - Proper categorization into "dimension", "fact", "metric", or "time_dimension"
{% if data_connection_tables %}**Data Connection Tables:** {{ data_connection_tables | join(", ") }}{% endif %}
**Categorization Guidelines:**
   - **dimension**: Categorical data used for grouping/filtering
     (e.g., product_name, customer_id, region)
   - **fact**: Numeric measures at row level (e.g., quantity, price, revenue)
   - **metric**: Aggregated business KPIs (e.g., total_revenue, avg_order_value)
   - **time_dimension**: Temporal data for time-based analysis (e.g., order_date, created_at)

**Quality Standards:**
   - Names should be clear and descriptive
   - Descriptions should be concise but informative and explain the table's and columns' purposes
   - Synonyms should cover common alternative terms and be user friendly. Note that technical
     terms can be used, but the context here is that non-technical users will be using
     the synonyms to reference the tables and columns in a non-technical way using natural language.
     Examples of synonyms for tables:
     - synonyms for orders_table: "orders", "customer orders", "order data"
     - synonyms for product_catalog: "products", "product list", "catalog"
     - synonyms for user_profiles: "users", "user data", "customer profiles"
     Examples of synonyms for columns:
     - synonyms for shipment_duration: "shipping time", "shipment time"
     - synonyms for product_name: "product name", "product"
     - synonyms for customer_id: "customer id", "customer"
     - synonyms for net_revenue: "revenue after discount", "net sales"
     - synonyms for qty_products: "quantity", "quantity of products"
     - synonyms for dt_created: "created at", "created date"
     - synonyms for total_amount: "total", "total amount"
   - Categorization should be accurate based on the column information

You will receive the current semantic model and should return an enhanced version with improvements.
Focus on making the model more useful so that later it's easier to generate SQL queries from natural
language based on the semantic data model.

**Output Instructions:**
Use the provided tool to submit your enhanced result. The tool will validate your output against
the expected schema. If your first attempt has validation errors, you will be asked to correct them.
""".strip()

        template = Template(template_str)
        return template.render(
            data_connection_tables=sorted(data_connection_tables) if data_connection_tables else None,
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

    def user_prompt(
        self,
        current_semantic_model: SemanticDataModelForLLM,
        data_connection_tables: set[str] | None = None,
    ) -> str:
        """Generate the user prompt for tables-only enhancement."""
        import json

        from jinja2 import Template

        # Define template as a local constant (pure layout, no conditionals)
        template_str = """
{{ opening }}

**Full Semantic Data Model (for context):**
```json
{{ semantic_model_json }}
```

{{ target_section }}
**Enhancement Requirements:**

**For the specified table(s):**
{% if not data_connection_tables %}   - Improve the logical name{% endif %}
   - Add/improve the description explaining the table's purpose
   - Add/change relevant synonyms that users might use to improve discoverability
{% if data_connection_tables %}   - Data connection tables: {{ ", ".join(data_connection_tables) }}{% endif %}

**Output Format:**
   Use the provided tool to return your enhanced result. The tool will validate your output.


**Important:**
- Ensure all synonyms are unique across the model
- For table/column logical names: make them SQL-safe (no spaces, special characters)
- Output ONLY the enhanced table metadata (no column information)
- The tool will validate your output against the expected JSON schema
""".strip()

        semantic_model_json = json.dumps(current_semantic_model.model_dump(), indent=2)

        # Build the opening line
        tables_list = ", ".join(f'"{t}"' for t in sorted(self.tables_to_enhance or []))
        opening = (
            f"Please improve ONLY the table metadata for the table(s) {tables_list} "
            "within the following semantic data model."
        )

        # Build the target section
        target_section = ""
        if self.tables_to_enhance:
            target_section = "**Target Tables to Enhance:**\n"
            target_section += "\n".join(f"- Table: {table_name}" for table_name in sorted(self.tables_to_enhance))

        # Render the template
        template = Template(template_str)
        return template.render(
            opening=opening,
            semantic_model_json=semantic_model_json,
            target_section=target_section,
            data_connection_tables=sorted(data_connection_tables or []),
        )

    def system_prompt(
        self,
        data_connection_tables: set[str] | None = None,
    ) -> str:
        """Generate the system prompt for tables-only enhancement."""
        from jinja2 import Template

        is_single_table = self.tables_to_enhance and len(self.tables_to_enhance) == 1

        template_str = """
You are an expert data analyst and semantic model designer.

Your task is to enhance a {{ task_description }} in a semantic data model by improving:

**Table Information:**
{% if not data_connection_tables %}   - Better logical name for the table{% endif %}
   - Improved description that explains the purpose of the table
   - Synonyms that users might use to refer to this table
{% if data_connection_tables %}**Data Connection Tables:** {{ data_connection_tables | join(", ") }}{% endif %}
**Quality Standards:**
   - Name should be clear and descriptive
   - Descriptions should be concise but informative and explain the table's purpose
   - Synonyms should cover common alternative terms and be user friendly. Note that technical
     terms can be used, but the context here is that non-technical users will be using
     the synonyms to reference the tables in a non-technical way using natural language.
     Examples of synonyms for tables:
     - synonyms for orders_table: "orders", "customer orders", "order data"
     - synonyms for product_catalog: "products", "product list", "catalog"
     - synonyms for user_profiles: "users", "user data", "customer profiles"

You will receive the full semantic model for context, but you should ONLY enhance the specific
table(s) that are highlighted. Focus on making the tables' metadata more useful so that later
it's easier to generate SQL queries from natural language based on the semantic data model.

**IMPORTANT:** You should NOT regenerate or modify any column information. Only provide metadata
for the table itself (name, description, synonyms).

**Output Instructions:**
Use the provided tool to submit your enhanced result. The tool will validate your output against
the expected schema. If your first attempt has validation errors, you will be asked to correct them.
""".strip()

        template = Template(template_str)
        return template.render(
            task_description="SINGLE TABLE'S METADATA" if is_single_table else "TABLE METADATA",
            data_connection_tables=sorted(data_connection_tables) if data_connection_tables else None,
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

    def user_prompt(
        self,
        current_semantic_model: SemanticDataModelForLLM,
        data_connection_tables: set[str] | None = None,
    ) -> str:
        """Generate the user prompt for columns-only enhancement."""
        import json

        from jinja2 import Template

        # Define template as a local constant (pure layout, no conditionals)
        template_str = """
Please improve ONLY the {{ target_items }} within the following semantic data model.

**Full Semantic Data Model (for context):**
```json
{{ semantic_model_json }}
```
{{ targets_section }}
**Enhancement Requirements:**


**For the specified column(s):**
{% if not data_connection_tables %}   - Improve the logical name{% endif %}
   - Add/improve the description explaining what the data represents
   - Add/change relevant synonyms that users might use to improve discoverability
   - Ensure proper categorization (dimension, fact, metric, time_dimension)
     (the initial categorization should be treated as a hint)


**Output Format:**
   Use the provided tool to return your enhanced result. The tool will validate your output.


**Important:**
- Ensure all synonyms are unique across the model
- For table/column logical names: make them SQL-safe (no spaces, special characters)
- Output ONLY the enhanced column(s)
- The tool will validate your output against the expected JSON schema
""".strip()

        semantic_model_json = json.dumps(current_semantic_model.model_dump(), indent=2)

        # Build the target items description
        if self.table_to_columns_to_enhance:
            items = []
            for table_name, columns in sorted(self.table_to_columns_to_enhance.items()):
                if len(columns) == 1:
                    items.append(f'column "{columns[0]}" in table "{table_name}"')
                else:
                    cols_list = ", ".join(f'"{c}"' for c in columns)
                    items.append(f'columns {cols_list} in table "{table_name}"')
            target_items = ", ".join(items)
        else:
            target_items = "specified columns"

        if self.table_to_columns_to_enhance:
            lines = ["", "**Target Columns to Enhance:**"]
            for table_name, columns in sorted(self.table_to_columns_to_enhance.items()):
                lines.append(f"- Table: {table_name}")
                for column_name in columns:
                    lines.append(f"  - Column: {column_name}")
            targets_section = "\n".join(lines)
        else:
            targets_section = ""

        # Render the template
        template = Template(template_str)
        return template.render(
            target_items=target_items,
            semantic_model_json=semantic_model_json,
            table_to_columns_to_enhance=sorted(
                self.table_to_columns_to_enhance.items() if self.table_to_columns_to_enhance else []
            ),
            data_connection_tables=sorted(data_connection_tables or []),
            targets_section=targets_section,
        )

    def system_prompt(
        self,
        data_connection_tables: set[str] | None = None,
    ) -> str:
        """Generate the system prompt for columns-only enhancement."""
        from jinja2 import Template

        is_single_column = (
            self.table_to_columns_to_enhance
            and sum(len(cols) for cols in self.table_to_columns_to_enhance.values()) == 1
        )
        is_multiple_columns = (
            self.table_to_columns_to_enhance
            and sum(len(cols) for cols in self.table_to_columns_to_enhance.values()) > 1
        )

        template_str = """
You are an expert data analyst and semantic model designer.

Your task is to enhance a {{ task_description }} in a semantic data model by improving:

**Column Information:**
{% if is_multiple_columns %}For each column:{% endif %}
{% if not data_connection_tables %}   - Better logical name for the column{% endif %}
   - Improved description that explains what the data represents
   - Synonyms that users might use to refer to this column
   - Proper categorization into "dimension", "fact", "metric", or "time_dimension"
{% if data_connection_tables %}**Data Connection Tables:** {{ data_connection_tables | join(", ") }}{% endif %}
**Categorization Guidelines:**
   - **dimension**: Categorical data used for grouping/filtering
     (e.g., product_name, customer_id, region)
   - **fact**: Numeric measures at row level (e.g., quantity, price, revenue)
   - **metric**: Aggregated business KPIs (e.g., total_revenue, avg_order_value)
   - **time_dimension**: Temporal data for time-based analysis (e.g., order_date, created_at)

**Quality Standards:**
   - Names should be clear and descriptive
   - Descriptions should be concise but informative and explain the column's purpose
   - Synonyms should cover common alternative terms and be user friendly. Note that technical
     terms can be used, but the context here is that non-technical users will be using
     the synonyms to reference the columns in a non-technical way using natural language.
     Examples of synonyms for columns:
     - synonyms for shipment_duration: "shipping time", "shipment time"
     - synonyms for product_name: "product name", "product"
     - synonyms for customer_id: "customer id", "customer"
     - synonyms for net_revenue: "revenue after discount", "net sales"
     - synonyms for qty_products: "quantity", "quantity of products"
     - synonyms for dt_created: "created at", "created date"
     - synonyms for total_amount: "total", "total amount"
   - Categorization should be accurate based on the column information

You will receive the full semantic model for context, but you should ONLY enhance the specific
column(s) that are highlighted. Focus on making the columns more useful so that later it's
easier to generate SQL queries from natural language based on the semantic data model.

**Output Instructions:**
Use the provided tool to submit your enhanced result. The tool will validate your output against
the expected schema. If your first attempt has validation errors, you will be asked to correct them.
""".strip()

        template = Template(template_str)
        return template.render(
            task_description="SINGLE COLUMN" if is_single_column else "MULTIPLE COLUMNS",
            is_multiple_columns=is_multiple_columns,
            data_connection_tables=sorted(data_connection_tables) if data_connection_tables else None,
        )


def create_strategy_from_mode(
    semantic_model: SemanticDataModel,
    mode: EnhancementMode,
    tables_to_enhance: set[str] | None = None,
    table_to_columns_to_enhance: dict[str, list[str]] | None = None,
) -> BaseStrategy:
    """Create a strategy from a mode."""
    if mode == "full":
        return FullStrategy(semantic_model, tables_to_enhance, table_to_columns_to_enhance)
    elif mode == "tables":
        return TablesOnlyStrategy(semantic_model, tables_to_enhance)
    elif mode == "columns":
        return ColumnsOnlyStrategy(semantic_model, tables_to_enhance, table_to_columns_to_enhance)
    else:
        raise ValueError(f"Unknown enhancement mode: {mode}")


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
