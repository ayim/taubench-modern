"""MCP Runtime configuration for deploying MCP server packages."""

from dataclasses import dataclass, field
from urllib.parse import urlparse

from agent_platform.core.configurations import Configuration, FieldMetadata


@dataclass(frozen=True)
class MCPRuntimeConfig(Configuration):
    """Configuration for MCP Runtime API."""

    mcp_runtime_api_url: str = field(
        default="http://mcp-runtime-url-not-specified",
        metadata=FieldMetadata(
            description="The URL of the MCP Runtime API for deploying MCP server packages.",
            env_vars=["SEMA4AI_AGENT_SERVER_MCP_RUNTIME_API_URL"],
        ),
    )

    def __post_init__(self) -> None:
        """Validate configuration after initialization."""
        # Validate that mcp_runtime_api_url is a valid URL
        try:
            parsed_url = urlparse(self.mcp_runtime_api_url)
            if not all([parsed_url.scheme, parsed_url.netloc]):
                raise ValueError(
                    f"Invalid mcp_runtime_api_url: {self.mcp_runtime_api_url}. "
                    "URL must include scheme (http:// or https://) and host.",
                )
        except Exception as e:
            raise ValueError(
                f"Invalid mcp_runtime_api_url: {self.mcp_runtime_api_url}. {e!s}",
            ) from e
