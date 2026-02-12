"""Verified query enhancer for improving metadata using LLM.

This module provides the VerifiedQueryEnhancer class that:
1. Generates prompts with SQL and SDM context
2. Calls the LLM to enhance parameter descriptions, query name, and NLQ
3. Validates the enhanced metadata using VerifiedQuery Pydantic model
4. Retries on validation errors with feedback
5. Falls back to original query if enhancement fails
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

import structlog

from agent_platform.server.semantic_data_models.verified_queries.enhancer.enhancer_prompts import (
    MINIMIZE_REASONING,
    TEMPERATURE,
)

if TYPE_CHECKING:
    from agent_platform.core.responses.response import ResponseMessage
    from agent_platform.core.semantic_data_model.types import (
        SemanticDataModel,
        VerifiedQuery,
    )
    from agent_platform.core.user import User
    from agent_platform.server.api.dependencies import StorageDependency
    from agent_platform.server.semantic_data_models.verified_queries.enhancer.enhancer_tool import (
        EnhancedVerifiedQueryMetadata,
    )

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Retry configuration
MAX_RETRY_ATTEMPTS = 3  # Maximum attempts to enhance with validation retries


class VerifiedQueryEnhancer:
    """Enhancer for verified query metadata using LLM.

    This class enhances parameter descriptions, query names, and NLQs by analyzing
    SQL queries in the context of semantic data models. It uses the LLM to generate
    business-friendly metadata while preserving SQL and parameter structure.
    """

    def __init__(
        self,
        user: User,
        storage: StorageDependency,
        agent_id: str,
        *,
        temperature: float = TEMPERATURE,
        minimize_reasoning: bool = MINIMIZE_REASONING,
        max_retry_attempts: int = MAX_RETRY_ATTEMPTS,
    ):
        """Initialize the verified query enhancer.

        Args:
            user: The user requesting the enhancement.
            storage: Storage dependency for database operations.
            agent_id: The agent ID to use for LLM calls.
            temperature: LLM temperature for generation (default: 0.3).
            minimize_reasoning: Whether to minimize reasoning tokens (default: True).
            max_retry_attempts: Maximum retry attempts on validation errors (default: 3).
        """
        self._user = user
        self._storage = storage
        self._agent_id = agent_id
        self._temperature = temperature
        self._minimize_reasoning = minimize_reasoning
        self._max_retry_attempts = max_retry_attempts

    async def enhance_verified_query(
        self,
        verified_query: VerifiedQuery,
        sdm: SemanticDataModel,
        sdm_context_tables: list[str] | None = None,
        existing_query_names: list[str] | None = None,
    ) -> VerifiedQuery:
        """Enhance a verified query's metadata using LLM.

        This method:
        1. Creates a prompt with SQL, parameters, and SDM context
        2. Calls LLM to generate enhanced metadata
        3. Validates enhanced metadata using VerifiedQuery model
        4. Retries on validation errors (max 3 attempts)
        5. Returns enhanced query or original on failure

        Args:
            verified_query: The verified query to enhance
            sdm: The semantic data model providing business context
            sdm_context_tables: Optional list of table names to include in context.
                If None, attempts to infer from SQL.
            existing_query_names: List of existing verified query names in the SDM
                to ensure the generated name is unique.

        Returns:
            Enhanced VerifiedQuery if successful, otherwise the original query.
        """
        logger.info(
            "Starting verified query enhancement",
            query_name=verified_query.name,
            num_parameters=len(verified_query.parameters or []),
        )

        start_time = time.monotonic()

        try:
            enhanced_query = await self._enhance_with_retry(
                verified_query=verified_query,
                sdm=sdm,
                sdm_context_tables=sdm_context_tables,
                existing_query_names=existing_query_names,
            )

            duration = time.monotonic() - start_time
            logger.info(
                "Verified query enhancement completed",
                query_name=enhanced_query.name,
                duration_seconds=f"{duration:.2f}",
                success=True,
            )

            return enhanced_query

        except Exception as e:
            duration = time.monotonic() - start_time
            logger.warning(
                "Verified query enhancement failed, returning original",
                query_name=verified_query.name,
                duration_seconds=f"{duration:.2f}",
                error=str(e),
                exc_info=True,
            )
            return verified_query

    async def _enhance_with_retry(
        self,
        verified_query: VerifiedQuery,
        sdm: SemanticDataModel,
        sdm_context_tables: list[str] | None,
        existing_query_names: list[str] | None,
    ) -> VerifiedQuery:
        """Attempt enhancement with retry logic on validation errors.

        Args:
            verified_query: The query to enhance
            sdm: The semantic data model
            sdm_context_tables: Optional list of table names for context
            existing_query_names: List of existing query names for uniqueness check

        Returns:
            Enhanced VerifiedQuery

        Raises:
            Exception: If all retry attempts fail
        """
        from pydantic import ValidationError

        from agent_platform.server.semantic_data_models.verified_queries.enhancer.enhancer_prompts import (
            create_enhancement_prompt,
        )
        from agent_platform.server.semantic_data_models.verified_queries.enhancer.enhancer_tool import (
            create_verified_query_enhancement_tool,
        )

        # Create initial prompt
        prompt = await create_enhancement_prompt(
            verified_query=verified_query,
            sdm=sdm,
            storage=self._storage,
            sdm_context_tables=sdm_context_tables,
            existing_query_names=existing_query_names,
        )

        # Create tool for LLM
        tool = create_verified_query_enhancement_tool()

        last_error: Exception | None = None

        for attempt in range(1, self._max_retry_attempts + 1):
            logger.info("Enhancement attempt", attempt=attempt, max_attempts=self._max_retry_attempts)

            try:
                # Call LLM
                response = await self._call_llm(prompt, tool)

                # Parse and merge enhanced metadata
                # This also validates the enhanced query using Pydantic
                validated_query = self._merge_enhanced_metadata(
                    original_query=verified_query,
                    llm_response=response,
                )

                logger.info("Enhancement validation successful", attempt=attempt)
                return validated_query

            except ValidationError as e:
                last_error = e
                error_messages = self._format_validation_errors(e)

                logger.warning(
                    "Enhancement validation failed",
                    attempt=attempt,
                    errors=error_messages,
                )

                # Add validation error feedback to prompt for retry
                if attempt < self._max_retry_attempts:
                    prompt = self._add_error_feedback_to_prompt(
                        prompt=prompt,
                        response=response,
                        validation_errors=error_messages,
                    )

            except Exception as e:
                last_error = e
                logger.error(
                    "Unexpected error during enhancement",
                    attempt=attempt,
                    error=str(e),
                    exc_info=True,
                )
                # Don't retry on unexpected errors
                break

        # All attempts failed
        raise Exception(f"Enhancement failed after {self._max_retry_attempts} attempts") from last_error

    async def _call_llm(
        self,
        prompt,
        tool,
    ) -> ResponseMessage:
        """Call the LLM with the enhancement prompt.

        Args:
            prompt: The PromptThread to send
            tool: The tool definition for the LLM

        Returns:
            ResponseMessage from the LLM
        """
        from fastapi import Request

        from agent_platform.server.api.private_v2.prompt import prompt_generate

        # Make a copy and add tool
        prompt_copy = prompt.copy()
        prompt_copy.tools = [tool]
        prompt_copy.tool_choice = tool.name

        # Call prompt_generate API
        response = await prompt_generate(
            prompt=prompt_copy,
            user=self._user,
            storage=self._storage,
            request=Request(scope={"type": "http", "method": "POST"}),
            agent_id=self._agent_id,
            minimize_reasoning=self._minimize_reasoning,
        )

        return response

    def _merge_enhanced_metadata(
        self,
        original_query: VerifiedQuery,
        llm_response: ResponseMessage,
    ) -> VerifiedQuery:
        """Merge enhanced metadata from LLM with original query data.

        This preserves SQL, parameter names, types, and example values while
        updating descriptions, query name, and NLQ.

        Args:
            original_query: The original VerifiedQuery
            llm_response: The LLM response containing enhanced metadata

        Returns:
            Enhanced VerifiedQuery (already validated)

        Raises:
            ValidationError: If the enhanced query fails Pydantic validation
        """

        # Extract enhanced metadata from LLM response
        enhanced_metadata = self._extract_enhanced_metadata(llm_response)

        # Prepare updates dictionary
        updates: dict[str, Any] = {
            "name": enhanced_metadata.query_name,
            "nlq": enhanced_metadata.nlq,
        }

        # Merge parameters: preserve all original data, only update descriptions
        if original_query.parameters:
            enhanced_param_desc_map = {p.name: p.description for p in enhanced_metadata.parameter_descriptions}

            updated_parameters = []
            for orig_param in original_query.parameters:
                # Use model_copy to update only the description
                updated_param = orig_param.model_copy(
                    update={
                        "description": enhanced_param_desc_map.get(
                            orig_param.name,
                            orig_param.description,  # Fall back to original if not found
                        )
                    }
                )
                updated_parameters.append(updated_param)

            updates["parameters"] = updated_parameters

        # Use model_copy to create enhanced query with validation
        return original_query.model_copy(update=updates)

    def _extract_enhanced_metadata(self, llm_response: ResponseMessage) -> EnhancedVerifiedQueryMetadata:
        """Extract enhanced metadata from LLM response.

        Args:
            llm_response: The response from the LLM

        Returns:
            EnhancedVerifiedQueryMetadata Pydantic model with enhanced metadata

        Raises:
            ValueError: If tool call not found or invalid
        """
        from agent_platform.core.responses.content import ResponseToolUseContent
        from agent_platform.server.semantic_data_models.verified_queries.enhancer.enhancer_tool import (
            EnhancedVerifiedQueryMetadata,
        )

        # Find tool call in response using isinstance check
        tool_call = None
        for content in llm_response.content:
            if isinstance(content, ResponseToolUseContent):
                tool_call = content
                break

        if not tool_call:
            raise ValueError("No tool call found in LLM response")

        # Parse tool input
        tool_input = tool_call.tool_input
        if not isinstance(tool_input, dict):
            raise ValueError(f"Tool input is not a dictionary: {type(tool_input)}")

        # Validate and return as Pydantic model
        return EnhancedVerifiedQueryMetadata.model_validate(tool_input)

    def _format_validation_errors(self, error: Exception) -> str:
        """Format validation errors for feedback to LLM.

        Args:
            error: The validation error

        Returns:
            Formatted error message
        """
        from pydantic import ValidationError

        if isinstance(error, ValidationError):
            error_lines = ["Validation errors:"]
            for err in error.errors():
                loc = " -> ".join(str(x) for x in err["loc"])
                msg = err["msg"]
                error_lines.append(f"  - {loc}: {msg}")
            return "\n".join(error_lines)
        else:
            return str(error)

    def _add_error_feedback_to_prompt(
        self,
        prompt,
        response: ResponseMessage,
        validation_errors: str,
    ):
        """Add validation error feedback to prompt for retry.

        Uses PromptThread's built-in append_response_and_error method to track
        the conversation history for retry attempts.

        Args:
            prompt: The PromptThread to update
            response: The LLM response that failed validation
            validation_errors: Formatted validation errors

        Returns:
            Updated PromptThread with error feedback
        """
        # Format the improvement request
        improvement_request = f"""The previous enhancement had validation errors:

{validation_errors}

Please correct these errors and try again. Ensure:
1. All parameter descriptions are 10-200 characters (brief but informative)
2. The query name uses ONLY letters, numbers, and spaces (no underscores, hyphens, or special characters)
3. The query name is max 50 characters and UNIQUE (not in existing names list)
4. The NLQ is a concise statement, 10-300 characters
"""

        # Use PromptThread's built-in method to append response and error
        prompt.append_response_and_error(response, improvement_request)

        return prompt
