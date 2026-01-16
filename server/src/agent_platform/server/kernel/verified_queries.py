# ruff: noqa: E501
"""Verified query tool creation for semantic data models.

This module handles the creation of dynamic tools from verified queries
defined in semantic data models. Each verified query becomes a callable tool
with proper parameter annotations.
"""

from __future__ import annotations

import typing
from dataclasses import dataclass, field

if typing.TYPE_CHECKING:
    from inspect import Parameter

    from agent_platform.core.data_frames.semantic_data_model_types import VerifiedQuery
    from agent_platform.core.tools.tool_definition import ToolDefinition


@dataclass
class VerifiedQueryInfo:
    """Information about a verified query and its associated tool.

    Stores the verified query along with its semantic data model context
    to avoid reverse engineering when creating tools.

    Attributes:
        verified_query: The verified query definition
        sdm_name: Name of the semantic data model this query belongs to
        dialect: SQL dialect used for this query (e.g., 'postgres', 'duckdb')
        tool_name: Name of the tool created for this verified query (set after tool creation)
    """

    verified_query: VerifiedQuery
    sdm_name: str
    dialect: str
    tool_name: str | None = field(default=None)


class VerifiedQueryToolBuilder:
    """Builds dynamic tools from verified queries with unique naming and SQL injection protection."""

    def __init__(self, existing_tool_names: dict[str, ToolDefinition]):
        """Initialize the builder with existing tools for uniqueness checking.

        Args:
            existing_tool_names: Dict mapping tool name -> ToolDefinition for O(1) duplicate checking
        """
        self._existing_tool_names = existing_tool_names

    def create_unique_tool_name(self, query_name: str) -> str:
        """Generate a unique tool name for a verified query.

        Slugifies the query name and adds a numeric suffix if needed to ensure uniqueness.
        Checks against all existing tools in self._existing_tool_names.

        Args:
            query_name: The name of the verified query

        Returns:
            A unique tool name (e.g., 'get_customers' or 'get_customers_1' if duplicate)
        """
        from sema4ai.common.text import slugify

        # Ensure valid tool name: alphanumeric + underscores
        base_name = slugify(query_name).replace("-", "_")

        # If unique, return as-is (O(1) dict lookup)
        if base_name not in self._existing_tool_names:
            return base_name

        # Add numeric suffix until unique
        counter = 1
        while f"{base_name}_{counter}" in self._existing_tool_names:
            counter += 1

        return f"{base_name}_{counter}"

    @staticmethod
    def build_tool_parameters(verified_query: VerifiedQuery) -> list[Parameter]:
        """Build the parameter list for a verified query tool.

        Args:
            verified_query: The verified query to build parameters for

        Returns:
            List of Parameter objects for the tool signature
        """
        from inspect import Parameter
        from typing import Annotated

        from agent_platform.core.data_frames.semantic_data_model_types import (
            QUERY_PARAMETER_TYPE_TO_PYTHON,
        )

        params_list: list[Parameter] = []

        # Add verified query specific parameters (all required, no defaults)
        if verified_query.parameters:
            for param in verified_query.parameters:
                python_type = QUERY_PARAMETER_TYPE_TO_PYTHON[param.data_type]

                # Build description with example value if available
                description = param.description
                if param.example_value is not None:
                    description = f"{description} (Example: {param.example_value})"

                params_list.append(
                    Parameter(
                        param.name,
                        Parameter.POSITIONAL_OR_KEYWORD,
                        annotation=Annotated[python_type, description],
                    )
                )

        # Add standard data frame parameters
        params_list.append(
            Parameter(
                "new_data_frame_name",
                Parameter.POSITIONAL_OR_KEYWORD,
                annotation=Annotated[
                    str,
                    """The name of the new data frame to create. IMPORTANT: It must be a valid variable name
                    such as 'my_data_frame', only ascii letters, numbers and underscores are allowed
                    and it cannot start with a number or be a python keyword. IMPORTANT: The name must be
                    unique in the thread (updating an existing data frame is not possible).""",
                ],
            )
        )
        params_list.extend(
            [
                Parameter(
                    "new_data_frame_description",
                    Parameter.POSITIONAL_OR_KEYWORD,
                    default=None,
                    annotation=Annotated[str | None, "Optional description for the data frame."],
                ),
                Parameter(
                    "num_samples",
                    Parameter.POSITIONAL_OR_KEYWORD,
                    default=10,
                    annotation=Annotated[
                        int,
                        """The number of samples to return from the newly created data frame (number of rows
                        to return). Default is 10 (max 500).""",
                    ],
                ),
            ]
        )

        return params_list

    @staticmethod
    def build_tool_docstring(verified_query: VerifiedQuery) -> str:
        """Build the docstring for a verified query tool.

        Args:
            verified_query: The verified query to build docstring for

        Returns:
            Formatted docstring in Python function style
        """
        # Simple docstring with just the NLQ description and return value explanation
        return f"""{verified_query.nlq}
This tool may return a status of success or needs_retry.

If the status indicates success, a new data frame is created with the query results,
and a sample of the data is returned (specified by num_samples).
If the status indicates needs_retry, you should inform the user of the failure,
along with the error message."""

    def create_and_add_tool(
        self,
        verified_query: VerifiedQuery,
        semantic_data_model_name: str,
        dialect: str,
        sql_executor_callback,
    ) -> str:
        """Create a tool definition for executing a verified query and add it to the tools list.

        Orchestrates the creation of a complete ToolDefinition by building parameters,
        docstring, and execution function. Parameters are safely substituted using
        sqlglot AST manipulation to prevent SQL injection.

        Automatically generates a unique tool name by checking existing tools.
        If a tool with the same base name already exists, adds a numeric suffix (_1, _2, etc.).

        Args:
            verified_query: The verified query to create a tool for
            semantic_data_model_name: The SDM name this query belongs to
            dialect: The SQL dialect for this query (e.g., 'postgres', 'snowflake').
                Must not be None.
            sql_executor_callback: Async callable that executes SQL and returns result dict.
                Signature: async (sql_query, new_data_frame_name, new_data_frame_description,
                           num_samples, semantic_data_model_name) -> dict

        Returns:
            The generated tool name
        """
        from inspect import Signature
        from typing import Any

        from agent_platform.core.tools.tool_definition import ToolDefinition
        from agent_platform.server.data_frames.sql_parameter_utils import (
            substitute_sql_parameters_safe,
        )

        # Build tool parameters and docstring using helper methods
        params_list = self.build_tool_parameters(verified_query)
        docstring = self.build_tool_docstring(verified_query)

        # Create the execution function
        async def execute_verified_query(**kwargs: Any) -> dict[str, Any]:
            """Execute this verified query with the provided parameters."""
            # Extract standard parameters
            new_data_frame_name = kwargs.pop("new_data_frame_name")
            new_data_frame_description = kwargs.pop("new_data_frame_description", None)
            num_samples = kwargs.pop("num_samples", 10)

            # Build parameter values dict for SQL substitution from provided kwargs
            query_params: dict[str, int | float | bool | str] = {}
            if verified_query.parameters:
                for param_def in verified_query.parameters:
                    param_name = param_def.name
                    if param_name in kwargs:
                        # Parameter was explicitly provided
                        query_params[param_name] = kwargs[param_name]
                    else:
                        # All parameters are required - this shouldn't happen if tool signature is correct
                        return {
                            "status": "needs_retry",
                            "message": (
                                f"Required parameter '{param_name}' not provided. "
                                f"All parameters must be explicitly specified."
                            ),
                            "data_frame_name": None,
                        }

            # Substitute parameters safely using sqlglot
            if verified_query.parameters:
                try:
                    sql_with_params = substitute_sql_parameters_safe(
                        sql=verified_query.sql,
                        param_values=query_params,
                        param_definitions=verified_query.parameters,
                        dialect=dialect,
                    )
                except ValueError as e:
                    return {
                        "status": "needs_retry",
                        "message": f"Parameter substitution failed: {e}",
                        "data_frame_name": None,
                    }
            else:
                # No parameters, use SQL as-is
                sql_with_params = verified_query.sql

            # Execute using callback
            # semantic_data_model_name is captured from closure - always uses the SDM this query belongs to
            return await sql_executor_callback(
                sql_query=sql_with_params,
                new_data_frame_name=new_data_frame_name,
                new_data_frame_description=new_data_frame_description,
                num_samples=num_samples,
                semantic_data_model_name=semantic_data_model_name,
            )

        # Generate unique tool name by checking existing tools
        # At this point, _existing_tool_names includes base tools + SQL strategy tools
        tool_name = self.create_unique_tool_name(verified_query.name)

        # Set function metadata
        execute_verified_query.__name__ = tool_name
        execute_verified_query.__doc__ = docstring
        execute_verified_query.__signature__ = Signature(params_list)  # type: ignore

        # Set annotations dict so ToolDefinition.from_callable can find type hints
        execute_verified_query.__annotations__ = {param.name: param.annotation for param in params_list}

        # Create ToolDefinition and add to existing tools
        tool = ToolDefinition.from_callable(
            execute_verified_query,
            category="internal-tool",
        )
        self._existing_tool_names[tool_name] = tool

        return tool_name
