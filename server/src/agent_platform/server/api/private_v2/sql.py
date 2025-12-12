import typing

from pydantic import BaseModel, Field

from agent_platform.core.thread import ThreadAgentMessage

if typing.TYPE_CHECKING:
    from agent_platform.core.thread.content.sql_generation import SQLGenerationDetails


class SQLGenerationDetailsResponse(BaseModel):
    """API model for SQL generation details stored in tool call metadata. Specifically
    for the OpenAPI specification.

    This model wraps SQLGenerationDetails to ensure it appears in the OpenAPI schema.
    It's stored in the metadata.execution.sql_generation_details field of a tool call.
    """

    agent_messages: list[ThreadAgentMessage] = Field(
        description="The messages from the SQL generation agent's thread. "
    )

    intent: str = Field(
        description="The intent of the SQL to generate.",
    )

    semantic_data_model_name: str = Field(
        description="The name of the semantic data model.",
    )

    @classmethod
    def from_core_model(cls, details: "SQLGenerationDetails") -> "SQLGenerationDetailsResponse":
        """Convert core SQLGenerationDetails to API model."""
        return cls(
            agent_messages=details.agent_messages,
            intent=details.intent,
            semantic_data_model_name=details.semantic_data_model_name,
        )

    model_config = {
        "json_schema_extra": {
            "description": (
                "Details about the SQL generation process, including the sub-agent's "
                "messages, intent, and semantic data model used. This is stored in "
                "the metadata.execution.sql_generation_details field of SQL generation "
                "tool calls."
            )
        }
    }
