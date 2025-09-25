from agent_platform.core.errors import ErrorCode, PlatformHTTPError


class ArtifactNotFoundError(PlatformHTTPError):
    """An artifact with the given ID was not found."""

    def __init__(self, message: str = "An artifact with the given ID was not found"):
        super().__init__(error_code=ErrorCode.NOT_FOUND, message=message)


class AgentWithNameAlreadyExistsError(PlatformHTTPError):
    """An agent with the given name already exists."""

    def __init__(self, message: str = "An agent with the given name already exists"):
        super().__init__(error_code=ErrorCode.CONFLICT, message=message)


class AgentNotFoundError(PlatformHTTPError):
    """An agent with the given ID was not found."""

    def __init__(self, message: str = "An agent with the given ID was not found"):
        super().__init__(error_code=ErrorCode.NOT_FOUND, message=message)


class ConfigNotFoundError(PlatformHTTPError):
    """Config with given config type was not found"""

    def __init__(self, message: str = "Config type not found"):
        super().__init__(error_code=ErrorCode.NOT_FOUND, message=message)


class ThreadNotFoundError(PlatformHTTPError):
    """A thread with the given ID was not found."""

    def __init__(self, message: str = "A thread with the given ID was not found"):
        super().__init__(error_code=ErrorCode.NOT_FOUND, message=message)


class UserAccessDeniedError(PlatformHTTPError):
    """The user does not have access to a given resource."""

    def __init__(self, message: str = "The user does not have access to this resource"):
        super().__init__(error_code=ErrorCode.FORBIDDEN, message=message)


class InvalidUUIDError(PlatformHTTPError):
    """The provided UUID is invalid."""

    def __init__(self, message: str = "The provided UUID is invalid"):
        super().__init__(error_code=ErrorCode.BAD_REQUEST, message=message)


class NoSystemUserError(PlatformHTTPError):
    """There is no system user."""

    def __init__(self, message: str = "No system user found"):
        super().__init__(error_code=ErrorCode.UNEXPECTED, message=message)


class UserNotFoundError(PlatformHTTPError):
    """A user with the given ID was not found."""

    def __init__(self, message: str = "A user with the given ID was not found"):
        super().__init__(error_code=ErrorCode.NOT_FOUND, message=message)


class MemoryNotFoundError(PlatformHTTPError):
    """A memory with the given ID was not found."""

    def __init__(self, message: str = "A memory with the given ID was not found"):
        super().__init__(error_code=ErrorCode.NOT_FOUND, message=message)


class ScopedStorageNotFoundError(PlatformHTTPError):
    """A scoped storage with the given ID was not found."""

    def __init__(
        self,
        message: str = "A scoped storage with the given ID was not found",
    ):
        super().__init__(error_code=ErrorCode.NOT_FOUND, message=message)


class RunNotFoundError(PlatformHTTPError):
    """A run with the given ID was not found."""

    def __init__(self, message: str = "A run with the given ID was not found"):
        super().__init__(error_code=ErrorCode.NOT_FOUND, message=message)


class RunStepNotFoundError(PlatformHTTPError):
    """A run step with the given ID was not found."""

    def __init__(self, message: str = "A run step with the given ID was not found"):
        super().__init__(error_code=ErrorCode.NOT_FOUND, message=message)


class ReferenceIntegrityError(PlatformHTTPError):
    """A reference integrity error occurred."""

    def __init__(self, message: str = "A reference integrity error occurred"):
        super().__init__(error_code=ErrorCode.BAD_REQUEST, message=message)


class RecordAlreadyExistsError(PlatformHTTPError):
    """A record with the given ID already exists."""

    def __init__(self, message: str = "A record with the given ID already exists"):
        super().__init__(error_code=ErrorCode.CONFLICT, message=message)


class UniqueFileRefError(PlatformHTTPError):
    """A file with the given file_ref already exists."""

    def __init__(
        self,
        file_ref: str,
        message: str = "A file with the given file_ref already exists",
    ):
        super().__init__(
            error_code=ErrorCode.CONFLICT, message=message, data={"file_ref": file_ref}
        )


class ThreadFileNotFoundError(PlatformHTTPError):
    """A file with the given ID was not found."""

    def __init__(self, message: str = "A file with the given ID was not found"):
        super().__init__(error_code=ErrorCode.NOT_FOUND, message=message)


class WorkItemFileNotFoundError(PlatformHTTPError):
    """A file with the given ID was not found."""

    def __init__(self, message: str = "A file with the given ID was not found"):
        super().__init__(error_code=ErrorCode.NOT_FOUND, message=message)


class UserPermissionError(PlatformHTTPError):
    """The user does not have permission to access the given resource."""

    def __init__(
        self,
        message: str = "The user does not have permission to access the given resource",
    ):
        super().__init__(error_code=ErrorCode.FORBIDDEN, message=message)


class StorageError(PlatformHTTPError):
    """Generic, unhandled storage error."""

    def __init__(self, message: str = "A storage error occurred"):
        super().__init__(error_code=ErrorCode.UNEXPECTED, message=message)


class WorkItemNotFoundError(PlatformHTTPError):
    """A work item with the given ID was not found."""

    def __init__(
        self,
        work_item_id: str,
        message: str = "A work item with the given ID was not found",
    ):
        super().__init__(
            error_code=ErrorCode.NOT_FOUND, message=message, data={"work_item_id": work_item_id}
        )


class MCPServerNotFoundError(PlatformHTTPError):
    """An MCP server with the given ID was not found."""

    def __init__(self, message: str = "An MCP server with the given ID was not found"):
        super().__init__(error_code=ErrorCode.NOT_FOUND, message=message)


class MCPServerWithNameAlreadyExistsError(PlatformHTTPError):
    """An MCP server with the given name already exists."""

    def __init__(self, message: str = "An MCP server with the given name already exists"):
        super().__init__(error_code=ErrorCode.CONFLICT, message=message)


class PlatformConfigNotFoundError(PlatformHTTPError):
    """A platform configuration with the given ID was not found."""

    def __init__(self, message: str = "A platform configuration with the given ID was not found"):
        super().__init__(error_code=ErrorCode.NOT_FOUND, message=message)


class PlatformConfigWithNameAlreadyExistsError(PlatformHTTPError):
    """A platform configuration with the given name already exists."""

    def __init__(
        self, message: str = "A platform configuration with the given name already exists"
    ):
        super().__init__(error_code=ErrorCode.CONFLICT, message=message)


class DIDSConnectionDetailsNotFoundError(PlatformHTTPError):
    """Document Intelligence DataServer has not been configured."""

    def __init__(self, message: str = "Document Intelligence DataServer has not been configured"):
        super().__init__(error_code=ErrorCode.PRECONDITION_FAILED, message=message)


class DocumentIntelligenceIntegrationNotFoundError(PlatformHTTPError):
    """A document intelligence integration with the given ID was not found."""

    def __init__(
        self, message: str = "A document intelligence integration with the given ID was not found"
    ):
        super().__init__(error_code=ErrorCode.NOT_FOUND, message=message)


class ConfigDecryptionError(PlatformHTTPError):
    """Failed to decrypt a configuration."""

    def __init__(self, message: str = "Failed to decrypt configuration"):
        super().__init__(error_code=ErrorCode.UNEXPECTED, message=message)


class DataConnectionNotFoundError(PlatformHTTPError):
    """A data connection with the given ID was not found."""

    def __init__(
        self, connection_id: str, message: str = "A data connection with the given ID was not found"
    ):
        super().__init__(
            error_code=ErrorCode.NOT_FOUND, message=message, data={"id": connection_id}
        )


class TrialAlreadyCanceledError(PlatformHTTPError):
    def __init__(self, connection_id: str, message: str = "Trial was already canceled"):
        super().__init__(
            error_code=ErrorCode.PRECONDITION_FAILED, message=message, data={"id": connection_id}
        )


class TrialNotFoundError(PlatformHTTPError):
    def __init__(
        self, connection_id: str, message: str = "A trial with the given ID was not found"
    ):
        super().__init__(
            error_code=ErrorCode.NOT_FOUND, message=message, data={"id": connection_id}
        )
