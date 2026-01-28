"""
Semantic data model enhancer for generatively enhancing semantic data models to improve
names, descriptions, synonyms, categorization, etc.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from agent_platform.server.semantic_data_models.enhancer.prompts import (
    MINIMIZE_REASONING,
    TEMPERATURE,
)

if TYPE_CHECKING:
    from pathlib import Path

    from tenacity import RetryCallState

    from agent_platform.core.data_frames.semantic_data_model_types import (
        LogicalTable,
        SemanticDataModel,
    )
    from agent_platform.core.prompts.prompt import Prompt
    from agent_platform.core.responses.response import ResponseMessage
    from agent_platform.core.user import User
    from agent_platform.server.api.dependencies import StorageDependency
    from agent_platform.server.semantic_data_models.enhancer.prompts import (
        PromptThread,
    )
    from agent_platform.server.semantic_data_models.enhancer.strategies import (
        BaseStrategy,
    )


# Retry configuration
MAX_RETRY_ATTEMPTS_FOR_OUTPUT_ERRORS = 2  # For formatting/parsing errors
MAX_RETRY_ATTEMPTS_FOR_QUALITY_ERRORS = 2  # For quality check errors (allows 1 retry)

# Can be set to a directory to see the input and output prompts and responses for further analysis.
DEFAULT_OUTPUT_DIR: Path | None = None  # Path("c:/temp/semantic_data_model_generator")

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class SemanticDataModelEnhancer:
    """
    API for enhancing semantic data models with the help of the LLM through the server
    prompt_generate API.
    """

    def __init__(
        self,
        user: User,
        storage: StorageDependency,
        agent_id: str,
        *,
        temperature: float = TEMPERATURE,
        minimize_reasoning: bool = MINIMIZE_REASONING,
        max_quality_check_attempts: int = MAX_RETRY_ATTEMPTS_FOR_QUALITY_ERRORS,
        max_output_formatting_attempts: int = MAX_RETRY_ATTEMPTS_FOR_OUTPUT_ERRORS,
        output_results_to: Path | None = DEFAULT_OUTPUT_DIR,
        enable_quality_check: bool = False,
    ):
        """
        Args:
            user: The user requesting the enhancement.
            storage: Storage dependency for database operations.
            agent_id: The agent ID to get the LLM to be used for the prompt generation.
            temperature: The temperature to use for the prompt generation, defaults to 0.5.
            minimize_reasoning: Whether to minimize reasoning in the prompt, defaults to False.
            max_quality_check_attempts: Maximum number of quality check retries, defaults to 2.
            max_output_formatting_attempts: Maximum number of output formatting retries,
                defaults to 2.
            output_results_to: A place to store the input and output prompts and responses
                for further analysis (debugging purposes).
            enable_quality_check: Whether to enable quality check after enhancement, defaults
                to False. Quality checks add significant time and can cause issues in partial
                enhancement scenarios. Disabling speeds up enhancement but may result in
                lower quality.
        """
        if output_results_to:
            self._output_results_to = self._get_next_dir_in_output_results_to(output_results_to)
        else:
            self._output_results_to = None

        self._user = user
        self._storage = storage
        self._agent_id = agent_id
        self._temperature = temperature
        self._minimize_reasoning = minimize_reasoning
        self._max_quality_check_attempts = max_quality_check_attempts
        self._max_output_formatting_attempts = max_output_formatting_attempts
        self._enable_quality_check = enable_quality_check

        self._enhancement_prompt_thread: PromptThread | None = None
        self._quality_check_prompt_thread: PromptThread | None = None

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
            with open(self._output_results_to / f"{prompt_type}_response_{iteration}.yaml", "w") as f:
                f.write(response)

    async def enhance_semantic_data_model(
        self,
        semantic_model: SemanticDataModel,
        tables_to_enhance: set[str] | None = None,
        table_to_columns_to_enhance: dict[str, list[str]] | None = None,
    ) -> SemanticDataModel:
        """
        Enhance the semantic data model with additional information using LLM.

        This method uses the `prompt_generate` API to iteratively improve the semantic data model
        by asking the LLM for better descriptions, names, synonyms, and categorization.

        Args:
            semantic_model: The semantic data model to enhance.
            tables_to_enhance: The names of the tables to enhance (required for "tables" mode).
            table_to_columns_to_enhance: Map from table name to the names of the columns
                to enhance (required for "columns" mode).

        Returns:
            Enhanced semantic data model.
        """
        import time

        from agent_platform.server.semantic_data_models.enhancer.prompts import (
            create_enhancement_prompt,
        )
        from agent_platform.server.semantic_data_models.enhancer.strategies import (
            create_strategy,
        )

        logger.info("Starting semantic data model enhancement")
        initial_time = time.monotonic()

        # Create the appropriate enhancer based on the parameters
        strategy = create_strategy(
            semantic_model,
            tables_to_enhance=tables_to_enhance,
            table_to_columns_to_enhance=table_to_columns_to_enhance,
        )

        # Set a new thread for the enhancement
        self._enhancement_prompt_thread = create_enhancement_prompt(
            semantic_model,
            strategy.mode,
            tables_to_enhance=tables_to_enhance,
            table_to_columns_to_enhance=table_to_columns_to_enhance,
            temperature=self._temperature,
            minimize_reasoning=self._minimize_reasoning,
        )
        try:
            semantic_model = await self._generate_enhancement_with_retry(strategy)
        except Exception as e:
            logger.error(f"Unexpected error during enhancement: {e}", exc_info=True)
            logger.warning("Returning the original semantic data model")
        finally:
            logger.info(f"Semantic data model enhancement completed in {time.monotonic() - initial_time:.2f} seconds")
        return semantic_model

    async def _generate_enhancement_with_retry(
        self,
        strategy: BaseStrategy,
    ) -> SemanticDataModel:
        """Tries to enhance a semantic data model with the given strategy.

        Args:
            strategy: The strategy instance that encapsulates mode-specific behavior.
        """
        import time

        from fastapi import Request
        from tenacity import (
            AsyncRetrying,
            retry_if_exception_type,
        )
        from tenacity.stop import stop_after_attempt

        from agent_platform.server.api.private_v2.prompt import prompt_generate
        from agent_platform.server.semantic_data_models.enhancer.errors import (
            LLMOutputResponseError,
            LLMResponseError,
        )
        from agent_platform.server.semantic_data_models.enhancer.type_defs import LLMOutputSchemas

        async def _attempt_generation(
            retry_state: RetryCallState,
        ) -> tuple[ResponseMessage, LLMOutputSchemas]:
            assert self._enhancement_prompt_thread is not None
            attempt_number = retry_state.attempt_number
            logger.info(f"Generation attempt {attempt_number}")

            self._enhancement_prompt_thread.update_prompt_with_previous_try(retry_state)

            # Get generation from LLM
            initial_time = time.monotonic()
            logger.info(">> Starting enhancement (prompt_generate)")
            self._write_input_prompt(self._enhancement_prompt_thread, "enhancement", iteration=attempt_number)

            response = await prompt_generate(
                # Don't send our current prompt thread or it will be finalized by the server.
                prompt=self._enhancement_prompt_thread.copy(),
                user=self._user,
                storage=self._storage,
                request=Request(scope={"type": "http", "method": "POST"}),
                agent_id=self._agent_id,
                minimize_reasoning=self._minimize_reasoning,
            )

            logger.info(f"<< Enhancement (prompt_generate) completed in {time.monotonic() - initial_time} seconds")

            # Use the enhancer to parse the response
            parsed_result = strategy.parse_response(response)

            # Log the response for debugging
            response_text = str(response.model_dump())
            self._write_output_response(response_text, "enhancement", iteration=attempt_number)
            logger.debug(f"LLM response for attempt {attempt_number}: {response_text}")

            return response, parsed_result

        try:
            async for attempt in AsyncRetrying(
                retry=retry_if_exception_type(LLMOutputResponseError),
                stop=stop_after_attempt(self._max_output_formatting_attempts),
                reraise=True,
            ):
                with attempt:
                    # Pass retry state to the attempt function so it can extract error info
                    _, parsed_result = await _attempt_generation(attempt.retry_state)

            # Use the enhancer to apply the enhancement to the semantic model
            # Note: The enhancer modifies the semantic_model in place.
            strategy.apply_enhancement(parsed_result)

        except LLMResponseError as e:
            # The lower-level enhancement retries all failed, can't do anything here.
            logger.error(f"Failed to enhance semantic data model: {e}", exc_info=True)
            logger.warning("Returning the original semantic data model")
            return strategy.semantic_model

        logger.info("Semantic data model enhancement completed successfully")
        return strategy.semantic_model


def reset_logical_names_to_physical_for_data_connections(
    semantic_model: SemanticDataModel,
) -> None:
    """
    Post-process an enhanced semantic data model to reset logical names to physical names
    for tables that are backed by data connections.

    For data connection-backed tables:
    - The logical table name is set to match the physical table name (base_table.table)
    - The logical column names are set to match the physical column expression (expr)

    This is useful when you want to preserve the original database naming convention
    instead of the LLM-generated friendly names for data connection sources.

    Args:
        semantic_model: The semantic data model to post-process. Modified in-place.
    """
    tables = semantic_model.tables or []

    for table in tables:
        base_table = table.get("base_table")
        if not base_table:
            continue

        # Only process tables backed by data connections
        data_connection_id = base_table.get("data_connection_id")
        if not data_connection_id:
            continue

        # Reset table name to physical table name
        physical_table_name = base_table.get("table")
        if physical_table_name:
            table["name"] = physical_table_name

        # Reset column names to physical column expressions
        _reset_column_names_to_physical(table)


def _reset_column_names_to_physical(table: LogicalTable) -> None:
    """
    Reset column names to match their physical expressions for a single table.

    Only resets names for dimensions, time_dimensions, and facts - NOT metrics.
    Metrics often have complex SQL expressions (e.g., SUM(oil) + SUM(gas) / 6.0)
    that are not valid column names, so their logical names should be preserved.

    Args:
        table: The logical table dict to process.
    """
    from agent_platform.core.data_frames.semantic_data_model_types import CATEGORIES

    # Skip metrics since their expr can be complex SQL expressions
    # that are not valid as column names
    categories_to_reset = [c for c in CATEGORIES if c != "metrics"]

    for category in categories_to_reset:
        columns = table.get(category) or []
        for column in columns:
            expr = column.get("expr")
            if expr:
                column["name"] = expr
