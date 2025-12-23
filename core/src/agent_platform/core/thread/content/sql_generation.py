from enum import StrEnum
from typing import TypedDict

from pydantic import BaseModel, Field, model_validator

from agent_platform.core.thread.messages import ThreadAgentMessage


class SQLGenerationStatus(StrEnum):
    """The status of a SQL generation."""

    SUCCESS = "success"
    """The SQL generation subagent was successful."""
    FAILED = "failed"
    """The SQL generation subagent failed to generate a SQL query."""
    NEEDS_INFO = "needs_info"
    """The SQL generation subagent needs additional information to generate the SQL query."""


class SqlGenerationFailedApproach(TypedDict):
    """A failed approach to generating a SQL query."""

    logical_sql_query: str
    """The logical SQL query that was attempted."""
    physical_sql_query: str
    """The physical SQL query that was attempted."""
    error: str
    """The error that occurred during the failed approach."""
    # TODO: We should enumerate these once we have a feeling of what common errors are.
    error_classification: str
    """The classification of the error that occurred during the failed approach, e.g.,
    "semantic_model_missing_required_field", "data_connection_not_found",
    "data_connection_connection_failed", etc."""
    explanation: str
    """The subagent's explanation of why this approach failed."""


class SQLGenerationContent(BaseModel):
    """Represents SQL generation results from a SQL generation subagent.

    This class handles the output from SQL generation subagents, encapsulating
    the SQL query, execution results, and any associated data frame information.
    It provides a structured way to communicate SQL generation results in the thread.
    """

    status: SQLGenerationStatus = Field(
        default=SQLGenerationStatus.SUCCESS,
        description="The status of the SQL generation",
    )
    """The status of the SQL generation"""

    sql_query: str | None = Field(
        default=None,
        description="The generated SQL query targeting semantic data model tables",
    )
    """The generated SQL query targeting semantic data model tables"""

    assumptions_used: str | None = Field(
        default=None,
        description=("Any assumptions used by the SQL generation subagent when generating the SQL query."),
    )
    """Any assumptions used by the SQL generation subagent when generating the SQL query."""

    message_to_parent: str | None = Field(
        default=None,
        description="A message from the SQL generation subagent to the parent agent. "
        "Used when the subagent needs clarification (e.g., 'Did you mean A1 or A2?') or "
        "cannot fulfill the request (e.g., 'No customer tables exist in this SDM.').",
    )
    """A message from the SQL generation subagent to the parent agent.

    Used when status is NEEDS_INFO to communicate either:
    - A clarification request: "You said A, but did you mean A1 or A2?"
    - An explanation of inability: "You asked about customers, but I don't have customer tables."
    """

    error_message: str | None = Field(
        default=None,
        description="An error message explaining why SQL generation completely failed. "
        "Used when status is FAILED to communicate unrecoverable errors.",
    )
    """An error message explaining why SQL generation completely failed.

    Used when status is FAILED. Unlike NEEDS_INFO (which implies the subagent could
    succeed with more information), FAILED means the subagent has given up and cannot
    generate SQL for this request.
    """

    @model_validator(mode="after")
    def validate_status_requirements(self) -> "SQLGenerationContent":
        """Validates that required fields are present based on status.

        Raises:
            ValueError: If required fields are missing based on status.
        """
        if self.status == SQLGenerationStatus.SUCCESS:
            if not self.sql_query:
                raise ValueError("sql_query is required for SUCCESS status")

        elif self.status == SQLGenerationStatus.NEEDS_INFO:
            if not self.message_to_parent:
                raise ValueError("message_to_parent is required for NEEDS_INFO status")

        return self

    def as_text_content(self) -> str:
        """Converts the SQL generation content to a human-readable text representation.

        Provides comprehensive output for terminal/testing visibility.
        """
        lines: list[str] = []
        lines.append("SQL GENERATION RESULT")

        # Status with emoji indicator
        status_indicators = {
            SQLGenerationStatus.SUCCESS: "✅ SUCCESS",
            SQLGenerationStatus.NEEDS_INFO: "❓ NEEDS INFO",
            SQLGenerationStatus.FAILED: "❌ FAILED",
        }
        lines.append(f"Status: {status_indicators.get(self.status, self.status.value)}")
        lines.append("-" * 60)

        if self.status == SQLGenerationStatus.SUCCESS:
            # Show SQL queries
            lines.append("\n📝 SQL (targeting semantic data model):")
            lines.append("```sql")
            lines.append(self.sql_query or "")
            lines.append("```")

            # Show assumptions if any
            if self.assumptions_used:
                lines.append("\n💭 ASSUMPTIONS MADE:")
                lines.append(self.assumptions_used)

        elif self.status == SQLGenerationStatus.NEEDS_INFO:
            lines.append("\n📨 MESSAGE TO PARENT:")
            lines.append(self.message_to_parent or "")

        elif self.status == SQLGenerationStatus.FAILED:
            # Also show error message if present
            if self.error_message:
                lines.append("\n⚠️  ERROR MESSAGE:")
                lines.append(self.error_message)

        return "\n".join(lines)


class SQLGenerationDetails(BaseModel):
    """Details about the SQL Agent's output."""

    agent_messages: list[ThreadAgentMessage] = Field(
        description="The messages from the SQL generation agent's thread.",
    )

    intent: str = Field(
        description="The intent of the SQL to generate.",
    )

    semantic_data_model_name: str = Field(
        description="The name of the semantic data model.",
    )
