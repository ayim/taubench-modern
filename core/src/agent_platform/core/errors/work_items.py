"""Work item specific errors."""

from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode


class WorkItemPayloadTooLargeError(PlatformHTTPError):
    """Raised when the work item payload exceeds the size limit."""

    def __init__(self, payload_size: int, allowed_payload_size: int):
        super().__init__(
            error_code=ErrorCode.BAD_REQUEST,
            message=(
                f"Work item payload size ({payload_size} KB) exceeds the allowed limit ({allowed_payload_size} KB)"
            ),
            data={
                "payload_size_kb": payload_size,
                "allowed_payload_size_kb": allowed_payload_size,
            },
        )


class WorkItemFileAttachmentTooLargeError(PlatformHTTPError):
    """Raised when the work item file attachment size exceeds the limit."""

    def __init__(self, payload_size: float, allowed_payload_size: float):
        super().__init__(
            error_code=ErrorCode.BAD_REQUEST,
            message=(
                f"Work item file attachment size ({payload_size} MB) exceeds the allowed limit "
                f"({allowed_payload_size} MB)"
            ),
            data={
                "payload_size_mb": payload_size,
                "allowed_payload_size_mb": allowed_payload_size,
            },
        )
