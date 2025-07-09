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
