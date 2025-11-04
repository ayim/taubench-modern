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

    from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel
    from agent_platform.core.prompts.prompt import Prompt
    from agent_platform.core.responses.response import ResponseMessage
    from agent_platform.core.user import User
    from agent_platform.server.api.dependencies import StorageDependency
    from agent_platform.server.semantic_data_models.enhancer.prompts import (
        EnhancementMode,
        PromptThread,
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

    def __init__(  # noqa: PLR0913
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
            with open(
                self._output_results_to / f"{prompt_type}_response_{iteration}.yaml", "w"
            ) as f:
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

        mode: EnhancementMode = "full"

        if tables_to_enhance or table_to_columns_to_enhance:
            if tables_to_enhance and table_to_columns_to_enhance:
                mode = "full"  # We have both, so, the full output is required
            elif tables_to_enhance:
                mode = "tables"
            elif table_to_columns_to_enhance:
                mode = "columns"
            else:
                raise ValueError("This should never be reachable (logic error)!")

        logger.info("Starting semantic data model enhancement")
        initial_time = time.monotonic()

        # Set a new thread for the enhancement
        self._enhancement_prompt_thread = create_enhancement_prompt(
            semantic_model,
            mode,
            tables_to_enhance=tables_to_enhance,
            table_to_columns_to_enhance=table_to_columns_to_enhance,
            temperature=self._temperature,
            minimize_reasoning=self._minimize_reasoning,
        )
        try:
            semantic_model = await self._generate_enhancement_with_retry(
                semantic_model, mode, tables_to_enhance, table_to_columns_to_enhance
            )
        except Exception as e:
            logger.error(f"Unexpected error during enhancement: {e}", exc_info=True)
            logger.warning("Returning the original semantic data model")
        finally:
            logger.info(
                f"Semantic data model enhancement completed in "
                f"{time.monotonic() - initial_time:.2f} seconds"
            )
        return semantic_model

    async def _generate_enhancement_with_retry(  # noqa: C901, PLR0915
        self,
        semantic_model: SemanticDataModel,
        mode: EnhancementMode = "full",
        tables_to_enhance: set[str] | None = None,
        table_to_columns_to_enhance: dict[str, list[str]] | None = None,
    ) -> SemanticDataModel:
        """Tries to enhance a semantic data model with different tiers of retry logic. A
        max quality check attempts and a max output formatting attempts. The quality check is the
        outside loop and the output formatting attempts is the inner loop. Upon getting a good
        result, the inner loop resets.

        Args:
            semantic_model: The semantic data model to enhance.
            mode: The enhancement mode (full, table, or column).
            tables_to_enhance: The names of the tables to enhance (required for "tables" mode).
            table_to_columns_to_enhance: Map from table name to the names of the columns
                to enhance (required for "columns" mode).
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
            EnhancementQualityInsufficientError,
            LLMOutputResponseError,
            LLMResponseError,
            QualityCheckError,
        )
        from agent_platform.server.semantic_data_models.enhancer.parse import (
            extract_response_text,
            update_columns_in_semantic_model,
            update_semantic_data_model_with_semantic_data_model_from_llm,
            update_tables_metadata_in_semantic_model,
            validate_and_parse_llm_response,
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
            self._write_input_prompt(
                self._enhancement_prompt_thread, "enhancement", iteration=attempt_number
            )

            response = await prompt_generate(
                # Don't send our current prompt thread or it will be finalized by the server.
                prompt=self._enhancement_prompt_thread.copy(),
                user=self._user,
                storage=self._storage,
                request=Request(scope={"type": "http", "method": "POST"}),
                agent_id=self._agent_id,
                minimize_reasoning=self._minimize_reasoning,
            )

            logger.info(
                f"<< Enhancement (prompt_generate) completed in "
                f"{time.monotonic() - initial_time} seconds"
            )

            parsed_result = validate_and_parse_llm_response(response, mode=mode)

            # Extract text content for logging/debugging
            response_text = extract_response_text(response)
            self._write_output_response(response_text, "enhancement", iteration=attempt_number)
            logger.debug(f"LLM response for attempt {attempt_number}: {response_text}")

            return response, parsed_result

        async def _attempt_enhancement(retry_state: RetryCallState):
            """Single enhancement attempt that will be retried by tenacity."""
            from agent_platform.server.semantic_data_models.enhancer.type_defs import (
                SemanticDataModelForLLM,
                TablesOutputSchema,
                TableToColumnsOutputSchema,
            )

            assert self._enhancement_prompt_thread is not None
            attempt_number = retry_state.attempt_number
            logger.info(f"Enhancement attempt {attempt_number}")

            self._enhancement_prompt_thread.update_prompt_with_previous_try(retry_state)

            # Use tenacity to generate a good response from the LLM.
            async for attempt in AsyncRetrying(
                retry=retry_if_exception_type(LLMOutputResponseError),
                stop=stop_after_attempt(self._max_output_formatting_attempts),
                reraise=True,
            ):
                with attempt:
                    # Pass retry state to the attempt function so it can extract error info
                    response, parsed_result = await _attempt_generation(attempt.retry_state)

            # Update the semantic model based on mode
            match mode:
                case "full":
                    assert isinstance(parsed_result, SemanticDataModelForLLM)
                    update_semantic_data_model_with_semantic_data_model_from_llm(
                        semantic_model,
                        parsed_result,
                        tables_to_enhance,
                        table_to_columns_to_enhance,
                    )
                case "tables":
                    assert isinstance(parsed_result, TablesOutputSchema)
                    update_tables_metadata_in_semantic_model(
                        semantic_model,
                        parsed_result,
                        tables_to_enhance,
                    )
                case "columns":
                    assert isinstance(parsed_result, TableToColumnsOutputSchema)
                    update_columns_in_semantic_model(
                        semantic_model,
                        parsed_result,
                        tables_to_enhance,
                        table_to_columns_to_enhance,
                    )
                case _:
                    raise ValueError(f"Generated invalid result type: {type(parsed_result)}")

            # Check quality of the enhancement
            if self._enable_quality_check:
                improvement_request = await self._check_enhancement_quality(
                    semantic_model,
                    attempt_number,
                    mode=mode,
                    tables_to_enhance=tables_to_enhance,
                    table_to_columns_to_enhance=table_to_columns_to_enhance,
                )

                if improvement_request:
                    logger.info("Quality check failed, requesting improvements")
                    raise EnhancementQualityInsufficientError(improvement_request, response)
            else:
                logger.info("Quality check disabled, skipping quality verification")

            return semantic_model

        try:
            # Use tenacity to retry on LLM response errors and quality check errors
            async for attempt in AsyncRetrying(
                retry=retry_if_exception_type(QualityCheckError),
                stop=stop_after_attempt(self._max_quality_check_attempts),
                reraise=True,
            ):
                with attempt:
                    # Pass retry state to the attempt function so it can extract error info
                    semantic_model = await _attempt_enhancement(attempt.retry_state)

            logger.info("Semantic data model enhancement completed successfully")
            return semantic_model
        except (LLMResponseError, QualityCheckError) as e:
            # Enhancement failed, likely due to poor formatting in LLM response.
            # Root cause: We don't provide output structure as a tool/function call, so the
            # LLM's training for structured output isn't being fully leveraged. Instead, we
            # rely on prompt engineering which is less reliable. This should be addressed
            # in the future by using structured outputs (tool calling or similar).
            # For now, we return the original model unchanged when enhancement fails.
            logger.error(f"Failed to enhance semantic data model: {e}", exc_info=True)
            logger.warning("Returning the original semantic data model")
            return semantic_model

    async def _check_enhancement_quality(
        self,
        enhanced_model: SemanticDataModel,
        iteration: int,
        mode: EnhancementMode = "full",
        tables_to_enhance: set[str] | None = None,
        table_to_columns_to_enhance: dict[str, list[str]] | None = None,
    ) -> str | None:
        """
        Check if the enhancement quality is sufficient.

        Note: This method does not attempt to retry on errors. If the quality check fails, it will
        return None.

        Returns:
            None if quality is sufficient, or an improvement request string if not.
        """
        import time

        from fastapi import Request

        from agent_platform.server.api.private_v2.prompt import prompt_generate
        from agent_platform.server.semantic_data_models.enhancer.errors import EmptyResponseError
        from agent_platform.server.semantic_data_models.enhancer.parse import extract_response_text
        from agent_platform.server.semantic_data_models.enhancer.prompts import (
            create_quality_check_prompt,
        )

        self._quality_check_prompt_thread = create_quality_check_prompt(
            enhanced_model,
            mode=mode,
            tables_to_enhance=tables_to_enhance,
            table_to_columns_to_enhance=table_to_columns_to_enhance,
            temperature=self._temperature,
            minimize_reasoning=self._minimize_reasoning,
        )

        try:
            initial_time = time.monotonic()
            logger.info(">> Starting quality check (prompt_generate)")
            self._write_input_prompt(
                self._quality_check_prompt_thread, "quality_check", iteration=iteration
            )
            response = await prompt_generate(
                prompt=self._quality_check_prompt_thread.copy(),
                user=self._user,
                storage=self._storage,
                request=Request(scope={"type": "http", "method": "POST"}),
                agent_id=self._agent_id,
                # We need to pass it here (the prompt value is overridden)
                minimize_reasoning=self._minimize_reasoning,
            )
            logger.info(
                f"<< Quality check (prompt_generate) completed in "
                f"{time.monotonic() - initial_time} seconds"
            )

            text_content = extract_response_text(response)
            self._write_output_response(text_content, "quality_check", iteration=iteration)
            quality_response_text = text_content.strip().upper()
            if quality_response_text.startswith(("PASSED", '"PASSED')):
                logger.info("LLM confirmed enhancement quality is sufficient")
                return None
            else:
                logger.info(
                    f"LLM suggested further improvements needed in the semantic "
                    f"data model: {text_content}"
                )
                return text_content
        except EmptyResponseError as e:
            logger.warning(f"Empty response from LLM while checking enhancement quality: {e}")
        except Exception as e:
            logger.error(f"Error checking enhancement quality: {e}")

        # If we can't check quality, assume it's okay
        return None
