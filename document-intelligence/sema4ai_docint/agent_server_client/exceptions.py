"""Exceptions for the agent-server-client library."""


class AgentServerError(Exception):
    """Base exception class for all agent-server-client errors."""

    pass


class DocumentClassificationError(AgentServerError):
    """Raised when a document cannot be classified into any of the available schemas."""

    def __init__(self, schema_name: str, available_schemas: list[str]):
        self.available_schemas = available_schemas
        super().__init__(
            f"Document could not be classified into any of the available schemas. "
            f"Got: '{schema_name}', available schemas: {', '.join(available_schemas)}"
        )
