"""Quota-related errors."""

from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode


class AgentQuotaExceededError(PlatformHTTPError):
    """Raised when the maximum number of agents has been reached."""

    def __init__(self, current_count: int, quota_limit: int):
        super().__init__(
            error_code=ErrorCode.TOO_MANY_REQUESTS,
            message=(
                f"Maximum number of agents ({quota_limit}) has been reached. "
                f"Current count: {current_count}"
            ),
            data={
                "current_count": current_count,
                "quota_limit": quota_limit,
                "error": "Agent quota exceeded",
            },
        )


class MCPServerQuotaExceededError(PlatformHTTPError):
    """Raised when the maximum number of MCP servers has been reached."""

    def __init__(self, current_count: int, quota_limit: int):
        super().__init__(
            error_code=ErrorCode.TOO_MANY_REQUESTS,
            message=(
                f"Maximum number of MCP servers ({quota_limit}) has been reached. "
                f"Current count: {current_count}"
            ),
            data={
                "current_count": current_count,
                "quota_limit": quota_limit,
                "error": "MCP server quota exceeded",
            },
        )
