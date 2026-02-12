"""LLM tool definition for verified query enhancement.

This module defines the tool schema that the LLM uses to return enhanced metadata
for verified queries. The schema is intentionally simpler than the full VerifiedQuery
model since we only enhance metadata (descriptions, name, NLQ), not SQL or parameters.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from agent_platform.core.tools.tool_definition import ToolDefinition


class EnhancedParameterDescription(BaseModel):
    """Enhanced description for a single parameter.

    This is a simplified schema containing only the parameter name and its
    enhanced description. Other parameter fields (data_type, example_value)
    are preserved from the original query.
    """

    name: str = Field(
        ...,
        description="The parameter name (must match an existing parameter in the query)",
    )
    description: str = Field(
        ...,
        min_length=10,
        max_length=200,
        description=(
            "One liner business-friendly description of what this parameter represents. "
            "Should be concise but informative, providing essential context from the semantic "
            "data model (e.g., 'Minimum race count threshold')"
        ),
    )


class EnhancedVerifiedQueryMetadata(BaseModel):
    """Enhanced metadata for a verified query.

    This contains only the metadata fields that should be enhanced by the LLM:
    - query_name: A descriptive name for the query
    - nlq: Natural language question the query answers
    - parameter_descriptions: Enhanced descriptions for each parameter

    SQL, parameter names, data types, and example values are NOT included here
    as they should remain unchanged.
    """

    query_name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description=(
            "A clear, descriptive name for the query that reflects its business purpose. "
            "Should be concise (2-6 words, max 50 characters) and use ONLY letters, numbers, and spaces. "
            "Do NOT use underscores, hyphens, or special characters. "
            "Must be UNIQUE within the semantic data model "
            "(e.g., 'High Performing Drivers', 'Customer Orders for specific product')"
        ),
    )

    nlq: str = Field(
        ...,
        min_length=10,
        max_length=300,
        description=(
            "A concise statement explaining what this query returns or does. "
            "Should be brief but informative, providing essential business context for tool documentation. "
            "Must be phrased as a statement. "
            "(e.g., 'Returns drivers with participation above specified race count', "
            "'Retrieves recent customer orders for a product')"
        ),
    )

    parameter_descriptions: list[EnhancedParameterDescription] = Field(
        ...,
        description=(
            "Enhanced descriptions for each parameter in the query. "
            "Must include all parameters present in the SQL query, no more and no less."
        ),
    )


def create_verified_query_enhancement_tool() -> ToolDefinition:
    """Create the LLM tool for verified query enhancement.

    Returns:
        A ToolDefinition instance that the LLM can use to return enhanced metadata.
    """
    from agent_platform.core.tools.tool_definition import ToolDefinition

    return ToolDefinition(
        name="enhance_verified_query",
        description=(
            "Enhance the metadata for a verified query by analyzing the SQL in the context "
            "of the semantic data model. Provide improved parameter descriptions, a descriptive "
            "query name, and a clear natural language description statement."
        ),
        input_schema=EnhancedVerifiedQueryMetadata.model_json_schema(mode="serialization"),
        category="internal-tool",
    )
