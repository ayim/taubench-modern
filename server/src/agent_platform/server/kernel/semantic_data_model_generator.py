# ruff: noqa: E501
# Ignoring long lines for the sake of readability in the prompt templates.
"""
Semantic data model generator for converting table/column information to semantic models.
"""

import json
import time
import typing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import Request
from structlog import get_logger

from agent_platform.core.data_frames.semantic_data_model_types import (
    BaseTable,
    Dimension,
    Fact,
    FileReference,
    LogicalTable,
    SemanticDataModel,
    TimeDimension,
)
from agent_platform.core.payloads.semantic_data_model_payloads import (
    ColumnInfo,
    DataConnectionInfo,
    FileInfo,
    TableInfo,
)
from agent_platform.core.prompts.content.text import PromptTextContent
from agent_platform.core.prompts.messages import PromptUserMessage
from agent_platform.core.prompts.prompt import Prompt
from agent_platform.core.responses.content.text import ResponseTextContent
from agent_platform.core.user import User
from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.api.private_v2.prompt import prompt_generate

if typing.TYPE_CHECKING:
    from agent_platform.server.kernel.semantic_data_model_generator_types import (
        SemanticDataModelForLLM,
    )

logger = get_logger(__name__)

# 1 Means we'll try in a single iteration
# -- although on output errors we'll have a single additional retry anyways
MAX_ITERATIONS = 1
TEMPERATURE = 0.5
MINIMIZE_REASONING = True

# Can be set to a directory to see the input and output prompts and responses for further analysis.
DEFAULT_OUTPUT_DIR: Path | None = None  # Path("c:/temp/semantic_data_model_generator")


@dataclass
class _EnhancementQualityCheckResult:
    passed: bool
    explanation: str | None = None


def _create_enhancement_system_prompt() -> str:
    """Create the system prompt for semantic data model enhancement."""

    return """
You are an expert data analyst and semantic model designer.
Your task is to enhance a semantic data model by improving:

1. **Table Information:**
   - Better logical names for tables
   - Improved descriptions that explain the purpose of the table
   - Synonyms that users might use to refer to these tables

2. **Column Information:**
   - Better logical names for columns
   - Improved descriptions that explain what the data represents
   - Synonyms that users might use to refer to these columns
   - Proper categorization into "dimension", "fact", "metric", and "time_dimension"

3. **Categorization Guidelines:**
   - **dimension**: Categorical data used for grouping/filtering
     (e.g., product_name, customer_id, region)
   - **fact**: Numeric measures at row level (e.g., quantity, price, revenue)
   - **metric**: Aggregated business KPIs (e.g., total_revenue, avg_order_value)
   - **time_dimension**: Temporal data for time-based analysis (e.g., order_date, created_at)

4. **Quality Standards:**
   - Names should be clear and descriptive
   - Descriptions should be concise but informative
   - Synonyms should cover common alternative terms and be user friendly. Note that technical
     terms can be used, but the context here is that non-technical users will be using
     the synonyms to reference the tables and columns in a non-technical way using natural language.
     Examples of synonyms:
     - synonyms for shipment_duration: "shipping time", "shipment time"
     - synonyms for product_name: "product name", "product"
     - synonyms for customer_id: "customer id", "customer"
     - synonyms for net_revenue: "revenue after discount", "net sales"
     - synonyms for qty_products: "quantity", "quantity of products"
     - synonyms for dt_created: "created at", "created date"
   - Categorization should be accurate based on the column information

You will receive the current semantic model and should return an enhanced version with improvements.
Focus on making the model more useful so that later it's easier to generate SQL queries from natural
language based on the semantic data model.
"""


def _create_enhancement_user_prompt(current_llm_model: "SemanticDataModelForLLM") -> str:
    """Create the user prompt for semantic data model enhancement."""
    from agent_platform.server.kernel.semantic_data_model_generator_types import (
        OUTPUT_SCHEMA_FORMAT,
    )

    return f"""
Please improve the following semantic data model by improving table and column information:

**Current Semantic Data Model:**
```json
{json.dumps(current_llm_model.model_dump(), indent=2)}
```

**Enhancement Requirements:**

1. **For each table:**
   - Improve the logical name
   - Add/improve the description explaining the table's purpose
   - Add/change relevant synonyms that users might use to improve discoverability

2. **For each column:**
   - Improve the logical name
   - Add/improve the description explaining what the data represents
   - Add/change relevant synonyms that users might use to improve discoverability
   - Ensure proper categorization (dimension, fact, metric, time_dimension)
     (the initial categorization should be treated as a hint)

3. **Output Format:**
   Return the enhanced model in JSON structure, but with improved:
   - `name` fields (better logical names)
   - `description` fields (clear, descriptive and concise descriptions)
   - `synonyms` fields (relevant alternative terms to improve discoverability,
      make them user friendly and consider the units of the data if applicable)
   - Proper categorization in `dimensions`, `facts`, `metrics`, `time_dimensions`
   - Optional fields that haven't changed should be ommitted in the output.
   - The `sample_values` field should always be ommitted in the output.

**Important:**
- Ensure all synonyms are unique across the model
- Make names SQL-safe (no spaces, special characters)
- Output the JSON in the following format: <semantic-data-model>...</semantic-data-model>.
- Do not include any other text except the <semantic-data-model>...</semantic-data-model> block.
- The output MUST be the semantic data model in JSON format and MUST match the JSON schema below:

{OUTPUT_SCHEMA_FORMAT}
"""


def _create_full_enhancement_prompt(
    semantic_model: "SemanticDataModel", enhancement_request_from_last_iteration: str | None
) -> Prompt:
    from agent_platform.server.kernel.semantic_data_model_generator_types import (
        create_semantic_data_model_for_llm_from_semantic_data_model,
    )

    model_for_llm = create_semantic_data_model_for_llm_from_semantic_data_model(
        semantic_model,
    )
    system_message = _create_enhancement_system_prompt()
    user_message = _create_enhancement_user_prompt(model_for_llm)

    messages = [PromptUserMessage(content=[PromptTextContent(text=user_message)])]

    enhancement_len = 0
    if enhancement_request_from_last_iteration:
        messages.append(
            PromptUserMessage(
                content=[PromptTextContent(text=enhancement_request_from_last_iteration)]
            )
        )
        enhancement_len = len(enhancement_request_from_last_iteration)

    prompt = Prompt(
        system_instruction=system_message,
        messages=messages,  # type: ignore
        temperature=TEMPERATURE,
        minimize_reasoning=MINIMIZE_REASONING,
    )
    len_summary = f"""
    Len summary for the semantic data model enhancement prompt:
    system_prompt_length: {len(system_message)}
    user_prompt_length: {len(user_message)}
    enhancement_request_length: {enhancement_len}
    """
    logger.info(len_summary)
    return prompt


def _extract_response_text(response_text: str) -> str:
    """Extract the json from the <semantic-data-model>...</semantic-data-model> block."""
    i = response_text.find("<semantic-data-model>")
    j = response_text.rfind("</semantic-data-model>")
    if i == -1 or j == -1:
        # We couldn't find the <semantic-data-model>...</semantic-data-model> block.
        logger.warning(
            f"Couldn't find the <semantic-data-model>...</semantic-data-model> block"
            f" in the response text: {response_text}"
        )
        raise ValueError(
            "Couldn't find the <semantic-data-model>...</semantic-data-model> block"
            " in the response. Please fix the response text and try again. Please pay extra attention"
            " to the output format and the JSON schema."
        )
    response_text = response_text[i + len("<semantic-data-model>") : j]
    response_text = response_text.strip()
    return response_text


class SemanticDataModelGenerator:
    """Generator for creating semantic data models from table/column information."""

    def __init__(self, output_results_to: Path | None = DEFAULT_OUTPUT_DIR):
        """
        Args:
            output_results_to: A place to store the input and output prompts and responses
                for further analysis (debugging purposes).
        """
        if output_results_to:
            self._output_results_to = self._get_next_dir_in_output_results_to(output_results_to)
        else:
            self._output_results_to = None

    @classmethod
    def _get_next_dir_in_output_results_to(cls, output_results_to: Path):
        """Get the next directory in the output results to."""
        base = "generation_results_"
        i = 0
        while True:
            i += 1
            next_dir = output_results_to / f"{base}{i:03d}"
            if not next_dir.exists():
                next_dir.mkdir(parents=True, exist_ok=True)
                return next_dir

    def _write_input_prompt(self, prompt: Prompt, prompt_type: str, iteration: int):
        """Write the input prompt to a file."""
        if self._output_results_to:
            with open(self._output_results_to / f"{prompt_type}_prompt_{iteration}.yaml", "w") as f:
                f.write(prompt.to_pretty_yaml(width=200))

    def _write_output_response(self, response: str, prompt_type: str, iteration: int):
        """Write the output response to a file."""
        if self._output_results_to:
            with open(
                self._output_results_to / f"{prompt_type}_response_{iteration}.yaml", "w"
            ) as f:
                f.write(response)

    async def generate_semantic_data_model(
        self,
        name: str,
        description: str | None,
        data_connections_info: list[DataConnectionInfo],
        files_info: list[FileInfo],
    ) -> SemanticDataModel:
        """Generate a semantic data model from data connections and files."""
        tables = []

        # Process data connections
        for data_connection_info in data_connections_info:
            for table_info in data_connection_info.tables_info:
                logical_table = self._create_logical_table_from_data_connection(
                    table_info, data_connection_info.data_connection_id
                )
                tables.append(logical_table)

        # Process files
        for file_info in files_info:
            for table_info in file_info.tables_info:
                logical_table = self._create_logical_table_from_file(
                    table_info, file_info.thread_id, file_info.file_ref, file_info.sheet_name
                )
                tables.append(logical_table)

        semantic_model: SemanticDataModel = {
            "name": name,
            "description": description,
            "tables": tables,
        }

        return semantic_model

    def _create_logical_table_from_data_connection(
        self, table_info: TableInfo, data_connection_id: str
    ) -> LogicalTable:
        """Create a logical table from a data connection table info."""
        base_table: BaseTable = {
            "data_connection_id": data_connection_id,
            "database": table_info.database,
            "schema": table_info.schema,
            "table": table_info.name,
        }

        return self._create_logical_table(table_info, base_table)

    def _create_logical_table_from_file(
        self, table_info: TableInfo, thread_id: str, file_ref: str, sheet_name: str | None
    ) -> LogicalTable:
        """Create a logical table from a file table info."""
        file_reference: FileReference = {
            "thread_id": thread_id,
            "file_ref": file_ref,
            "sheet_name": sheet_name,
        }

        base_table: BaseTable = {
            "file_reference": file_reference,
            "table": table_info.name,
        }

        return self._create_logical_table(table_info, base_table)

    def _create_logical_table(self, table_info: TableInfo, base_table: BaseTable) -> LogicalTable:
        """Create a logical table from table info and base table."""
        dimensions: list[Dimension] = []
        facts: list[Fact] = []
        time_dimensions: list[TimeDimension] = []

        for column in table_info.columns:
            if self._is_dimension_column(column):
                dimension = self._create_dimension(column)
                dimensions.append(dimension)
            elif self._is_time_column(column):
                time_dim = self._create_time_dimension(column)
                time_dimensions.append(time_dim)
            elif self._is_numeric_column(column):
                fact = self._create_fact(column)
                facts.append(fact)
            else:
                dimension = self._create_dimension(column)
                dimensions.append(dimension)

        logical_table: LogicalTable = {
            "name": table_info.name,
            "base_table": base_table,
            "description": table_info.description,
            "dimensions": dimensions,
            "facts": facts,
            "time_dimensions": time_dimensions,
        }

        return logical_table

    def _is_dimension_column(self, column: ColumnInfo) -> bool:
        """Check if a column is a dimension column based on its data type."""
        name_lower = column.name.lower()
        if name_lower.endswith("_id") or "name" in name_lower:
            return True
        return False

    def _is_time_column(self, column: ColumnInfo) -> bool:
        """Check if a column is a time column based on its data type."""
        time_types = {
            "timestamp",
            "datetime",
            "date",
            "time",
            "timestamptz",
            "timetz",
            "timestamp with time zone",
            "timestamp without time zone",
        }
        return column.data_type.lower() in time_types

    def _is_numeric_column(self, column: ColumnInfo) -> bool:
        """Check if a column is numeric based on its data type."""
        numeric_types = {
            "int",
            "integer",
            "bigint",
            "smallint",
            "tinyint",
            "float",
            "double",
            "real",
            "numeric",
            "decimal",
            "money",
            "currency",
        }
        return column.data_type.lower() in numeric_types

    def _create_dimension(self, column: ColumnInfo) -> Dimension:
        """Create a dimension from column info."""
        dimension: Dimension = {
            "name": column.name,
            "expr": column.name,
            "data_type": column.data_type,
        }

        if column.description:
            dimension["description"] = column.description
        if column.synonyms:
            dimension["synonyms"] = column.synonyms
        if column.sample_values:
            dimension["sample_values"] = self._get_sample_values(column.sample_values)

        return dimension

    def _create_fact(self, column: ColumnInfo) -> Fact:
        """Create a fact from column info."""
        fact: Fact = {
            "name": column.name,
            "expr": column.name,
            "data_type": column.data_type,
        }

        if column.description:
            fact["description"] = column.description
        if column.synonyms:
            fact["synonyms"] = column.synonyms
        if column.sample_values:
            fact["sample_values"] = self._get_sample_values(column.sample_values)

        return fact

    def _create_time_dimension(self, column: ColumnInfo) -> TimeDimension:
        """Create a time dimension from column info."""
        time_dimension: TimeDimension = {
            "name": column.name,
            "expr": column.name,
            "data_type": column.data_type,
        }

        if column.description:
            time_dimension["description"] = column.description
        if column.synonyms:
            time_dimension["synonyms"] = column.synonyms
        if column.sample_values:
            time_dimension["sample_values"] = self._get_sample_values(column.sample_values)

        return time_dimension

    def _get_sample_values(
        self, sample_values: list[Any] | None
    ) -> list[str | int | float | bool | None] | None:
        """Get sample values as strings."""
        from types import NoneType

        if sample_values is None:
            return None
        ret = []
        for value in sample_values:
            if isinstance(value, str | int | float | bool | NoneType):
                ret.append(value)
            else:
                ret.append(str(value))
        return ret

    async def enhance_semantic_data_model(  # noqa: C901, PLR0915, PLR0912
        self,
        semantic_model: SemanticDataModel,
        user: User,
        storage: StorageDependency,
        agent_id: str,
    ) -> SemanticDataModel:
        """
        Enhance the semantic data model with additional information using LLM.

        This method uses the `prompt_generate` API to iteratively improve the semantic data model
        by asking the LLM for better descriptions, names, synonyms, and categorization.

        Args:
            semantic_model: The semantic data model to enhance.
            user: The user requesting the enhancement.
            storage: Storage dependency for database operations.
            agent_id: The agent ID to get the LLM to be used for the prompt generation.

        Returns:
            Enhanced semantic data model.
        """
        from agent_platform.server.kernel.semantic_data_model_generator_types import (
            SemanticDataModelForLLM,
            update_semantic_data_model_with_semantic_data_model_from_llm,
        )

        logger.info("Starting semantic data model enhancement")

        enhancement_done = False

        max_iterations = MAX_ITERATIONS

        prompt = _create_full_enhancement_prompt(semantic_model, "")

        iteration = 0
        while iteration < max_iterations:
            iteration += 1
            logger.info(f"Enhancement iteration {iteration}/{max_iterations}")

            try:
                # Get enhancement from LLM
                initial_time = time.monotonic()
                logger.info(">> Starting enhancement (prompt_generate)")
                self._write_input_prompt(prompt, "enhancement", iteration=iteration)
                response = await prompt_generate(
                    prompt=prompt,
                    user=user,
                    storage=storage,
                    request=Request(scope={"type": "http", "method": "POST"}),
                    agent_id=agent_id,
                    # We need to pass it here (the prompt value is overridden)
                    minimize_reasoning=MINIMIZE_REASONING,
                )
                logger.info(
                    f"<< Enhancement (prompt_generate) completed in "
                    f"{time.monotonic() - initial_time} seconds"
                )

                if not response.content:
                    logger.warning(f"No content in response for iteration {iteration}")
                    if max_iterations <= 1:
                        max_iterations += 1  # Allow one retry if we only had one iteration
                    continue  # Retry to fix

                # Extract text content
                text_content = [
                    c.text for c in response.content if isinstance(c, ResponseTextContent)
                ]
                if not text_content:
                    logger.warning(f"No text content in response for iteration {iteration}")
                    if max_iterations <= 1:
                        max_iterations += 1  # Allow one retry if we only had one iteration
                    continue  # Retry to fix

                try:
                    response_text = _extract_response_text(text_content[-1])
                except ValueError as e:
                    prompt.messages.append(
                        PromptUserMessage(content=[PromptTextContent(text=f"{e}")])
                    )
                    if max_iterations <= 1:
                        max_iterations += 1  # Allow one retry if we only had one iteration
                    continue  # Retry with fix request!

                self._write_output_response(response_text, "enhancement", iteration=iteration)
                logger.debug(f"LLM response for iteration {iteration}: {response_text}")

                # Parse the enhanced model
                try:
                    enhanced_model_dict = json.loads(response_text)
                    logger.info(
                        f"Successfully parsed json enhanced model for iteration {iteration}."
                    )
                except json.JSONDecodeError as e:
                    prompt.messages.append(
                        PromptUserMessage(
                            content=[
                                PromptTextContent(
                                    text=f"Please retry fixing the following error: failed"
                                    f" to parse JSON response. Error: {e}"
                                )
                            ]
                        )
                    )

                    logger.error(
                        f"Failed to parse JSON response for iteration {iteration}: {e}\n"
                        f"Response from LLM: {response_text}"
                    )
                    if max_iterations <= 1:
                        max_iterations += 1  # Allow one retry if we only had one iteration
                    continue  # Retry with fix request!

                try:
                    semantic_data_model_from_llm = SemanticDataModelForLLM.model_validate(
                        enhanced_model_dict
                    )
                except Exception as e:
                    prompt.messages.append(
                        PromptUserMessage(
                            content=[
                                PromptTextContent(
                                    text=f"Please retry fixing the following error: semantic data"
                                    f" model does not match the expected schema. Error: {e}"
                                )
                            ]
                        )
                    )

                    logger.error(
                        f"Failed to parse load json as SemanticDataModelForLLM for iteration"
                        f" {iteration}: {e}\n"
                        f"Found response: {enhanced_model_dict}"
                    )
                    if max_iterations <= 1:
                        max_iterations += 1  # Allow one retry if we only had one iteration
                    continue  # Retry with fix request!

                update_semantic_data_model_with_semantic_data_model_from_llm(
                    semantic_model, semantic_data_model_from_llm
                )
                enhancement_done = True

                # Commented out: let's see how well we do things with a single iteration
                # before we start doing multiple iterations.
                # Check if we should continue iterating
                if iteration < max_iterations:
                    # Ask LLM if the improvements are good enough
                    quality_check = await self._check_enhancement_quality(
                        semantic_model, user, storage, agent_id, iteration
                    )
                    if quality_check.passed:
                        logger.info("LLM confirmed enhancement quality is sufficient")
                        return semantic_model
                    else:
                        logger.info("LLM suggested further improvements needed")
                        prompt = _create_full_enhancement_prompt(
                            semantic_model, quality_check.explanation
                        )

            except Exception as e:
                logger.error(f"Error in enhancement iteration {iteration}: {e}")
                break

        if not enhancement_done:
            logger.warning(
                "It was not possible to enhance the semantic data model. Returning the original model."
            )
        return semantic_model

    async def _check_enhancement_quality(
        self,
        enhanced_model: SemanticDataModel,
        user: User,
        storage: StorageDependency,
        agent_id: str,
        iteration: int,
    ) -> _EnhancementQualityCheckResult:
        """Check if the enhancement quality is sufficient."""
        quality_prompt = Prompt(
            minimize_reasoning=True,
            system_instruction="""
You are a quality reviewer for semantic data model enhancements.
Review the semantic data model and determine if the improvements are acceptable.

Consider: clarity of names, usefulness of descriptions, relevance of synonyms,
and proper categorization (dimension, fact, metric, time_dimension).

Notes:

Only check for quality the following fields:
- name
- description
- synonyms
- category in which the column is (dimension, fact, metric, time_dimension)

All the other fields MUST NOT be checked for quality (as they are immutable and just
presented as information to build the fields above).

All selected tables and columns should be kept (just the names can be changed).
""",
            messages=[
                PromptUserMessage(
                    content=[
                        PromptTextContent(
                            text=f"""
Please review this enhanced semantic data model and determine if there are additional
improvements needed:

```json
{json.dumps(enhanced_model, indent=2)}
```

Respond with only "PASSED" if the enhancements are good enough.
If the enhancements are not good enough, please reply with "Please improve: <explanation>"
where <explanation> is a detailed explanation of what needs to be improved.
"""
                        )
                    ]
                )
            ],
            temperature=TEMPERATURE,
        )

        try:
            initial_time = time.monotonic()
            logger.info(">> Starting quality check (prompt_generate)")
            self._write_input_prompt(quality_prompt, "quality_check", iteration=iteration)
            response = await prompt_generate(
                quality_prompt,
                user=user,
                storage=storage,
                request=Request(scope={"type": "http", "method": "POST"}),
                agent_id=agent_id,
                # We need to pass it here (the prompt value is overridden)
                minimize_reasoning=MINIMIZE_REASONING,
            )
            logger.info(
                f"<< Quality check (prompt_generate) completed in "
                f"{time.monotonic() - initial_time} seconds"
            )

            if response.content:
                text_content = [
                    c.text for c in response.content if isinstance(c, ResponseTextContent)
                ]
                if text_content:
                    self._write_output_response(
                        text_content[-1], "quality_check", iteration=iteration
                    )
                    quality_response_check_passed = text_content[-1].strip().upper()
                    if quality_response_check_passed.startswith(("PASSED", '"PASSED')):
                        logger.info("LLM confirmed enhancement quality is sufficient")
                        return _EnhancementQualityCheckResult(passed=True)
                    else:
                        logger.info(
                            f"LLM suggested further improvements needed in the semantic "
                            f"data model: {text_content[-1]}"
                        )
                        return _EnhancementQualityCheckResult(
                            passed=False, explanation=text_content[-1]
                        )
        except Exception as e:
            logger.error(f"Error checking enhancement quality: {e}")

        return _EnhancementQualityCheckResult(passed=True)
