"""Prompt generation for verified query enhancement.

This module generates prompts that provide the LLM with:
- SQL query to analyze
- Current parameter metadata (names, types, example values, descriptions)
- Semantic data model context (tables, columns, descriptions)
- Instructions for enhancement
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from agent_platform.core.errors import ErrorCode, PlatformError
from agent_platform.core.prompts.messages import (
    PromptTextContent,
    PromptUserMessage,
)
from agent_platform.server.kernel.semantic_data_model import (
    get_dialect_from_semantic_data_model,
    summarize_data_model,
    summarize_verified_query,
)
from agent_platform.server.semantic_data_models.enhancer.prompts import PromptThread

if TYPE_CHECKING:
    from agent_platform.core.semantic_data_model.types import (
        SemanticDataModel,
        VerifiedQuery,
    )
    from agent_platform.server.storage.base import BaseStorage

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# LLM generation parameters
TEMPERATURE = 0.3  # Lower temperature for more focused, consistent results
MINIMIZE_REASONING = True  # Minimize reasoning to reduce token usage


async def create_enhancement_prompt(
    verified_query: VerifiedQuery,
    sdm: SemanticDataModel,
    storage: BaseStorage,
    sdm_context_tables: list[str] | None = None,
    existing_query_names: list[str] | None = None,
) -> PromptThread:
    """Create a prompt for enhancing verified query metadata.

    Args:
        verified_query: The verified query to enhance (contains SQL, parameters, name, NLQ)
        sdm: The semantic data model providing business context
        storage: Storage instance to fetch data connections for dialect detection
        sdm_context_tables: Optional list of table names to include in context.
            If None, includes all tables mentioned in the SQL.
        existing_query_names: List of existing verified query names in the SDM
            to ensure uniqueness.

    Returns:
        A PromptThread configured for verified query enhancement with retry support.
    """
    system_instruction = _create_system_instruction()
    user_message = await _create_user_message(
        verified_query=verified_query,
        sdm=sdm,
        storage=storage,
        sdm_context_tables=sdm_context_tables,
        existing_query_names=existing_query_names,
    )

    return PromptThread(
        system_instruction=system_instruction,
        messages=[user_message],
        temperature=TEMPERATURE,
        minimize_reasoning=MINIMIZE_REASONING,
    )


def _create_system_instruction() -> str:
    """Create the system instruction for the LLM on enhancement.

    Returns:
        System instruction string with enhancement instructions.
    """
    return """You are an expert at analyzing SQL queries in the context of semantic data models to \
create clear, business-friendly metadata.

Your task is to enhance verified query metadata by:

1. **Parameter Descriptions**: Analyze each parameter placeholder (e.g., :param_name) in the SQL \
and provide a one liner business-friendly description of what it represents. Descriptions should be \
concise but informative (ideally 10-50 words). Use the semantic data model context to understand \
the business meaning.

2. **Query Name**: Create a concise, descriptive name (2-6 words, max 50 characters) that \
reflects the query's business purpose.
   - Use ONLY letters, numbers, and spaces (e.g., 'High Performing Drivers', 'Recent Orders by Region')
   - The name must be UNIQUE within the semantic data model (check existing query names provided)

3. **Query Description (NLQ)**: Write a concise statement explaining what this query returns or does. \
Should be brief but informative (ideally 15-75 words), incorporating essential business context \
from the semantic data model. Must be phrased as a statement, not a question.

**Important Guidelines:**
- PRESERVE the parameter names, data types, and example values exactly as provided
- DO NOT modify the SQL query in any way
- Focus on making the metadata clear, concise, and business-friendly
- Keep descriptions brief - avoid unnecessary verbosity
- Ensure all parameters in the SQL have descriptions, no more and no less
- Query name must be UNIQUE - do not use any names from the existing queries list

**Output:**
Use the enhance_verified_query tool to return the enhanced metadata."""


async def _create_user_message(
    verified_query: VerifiedQuery,
    sdm: SemanticDataModel,
    storage: BaseStorage,
    sdm_context_tables: list[str] | None = None,
    existing_query_names: list[str] | None = None,
) -> PromptUserMessage:
    """Create the user message with query details, parameters, and SDM context.

    Args:
        verified_query: The verified query to enhance
        sdm: The semantic data model
        storage: Storage instance to fetch data connections for dialect detection
        sdm_context_tables: Optional list of table names to include in context
        existing_query_names: List of existing verified query names for uniqueness check

    Returns:
        User message with all context needed for enhancement.
    """
    # Detect SQL dialect/engine from the semantic data model
    engine = await get_dialect_from_semantic_data_model(sdm, storage)

    # Raise error if no engine is detected
    if not engine:
        raise PlatformError(
            error_code=ErrorCode.UNEXPECTED,
            message=("Cannot detect SQL dialect from semantic data model."),
        )

    # Extract SDM context using the shared summarize_data_model function
    sdm_context = summarize_data_model(sdm, engine=engine, table_names=sdm_context_tables)

    # Format verified query using shared function
    query_summary = summarize_verified_query(verified_query)

    # Format existing query names
    existing_names_text = _format_existing_query_names(existing_query_names)

    user_text = f"""Please enhance the metadata for the following verified query.

## Semantic Data Model Context

{sdm_context}

## Query

{query_summary}

## Existing Query Names

{existing_names_text}

## Task

Analyze the SQL query in the context of the semantic data model and enhance:
1. Parameter descriptions (one liner business-friendly description)
2. Query name (descriptive, concise, and UNIQUE - must not match any existing query name)
3. Query Description (NLQ) (clear and business-focused)

Use the enhance_verified_query tool to provide the enhanced metadata.
"""

    return PromptUserMessage(content=[PromptTextContent(text=user_text.strip())])


def _format_existing_query_names(existing_names: list[str] | None) -> str:
    """Format existing query names for the prompt.

    Args:
        existing_names: List of existing verified query names

    Returns:
        Formatted string with existing query names.
    """
    if not existing_names:
        return "No existing queries"

    names_list = "\n".join(f"- {name}" for name in sorted(existing_names))
    return names_list
