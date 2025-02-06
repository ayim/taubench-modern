from fastapi import HTTPException


class AgentWithNameAlreadyExistsError(HTTPException):
    """An agent with the given name already exists."""

    def __init__(self, detail: str = "An agent with the given name already exists"):
        super().__init__(status_code=409, detail=detail)


class AgentNotFoundError(HTTPException):
    """An agent with the given ID was not found."""

    def __init__(self, detail: str = "An agent with the given ID was not found"):
        super().__init__(status_code=404, detail=detail)


class ThreadNotFoundError(HTTPException):
    """A thread with the given ID was not found."""

    def __init__(self, detail: str = "A thread with the given ID was not found"):
        super().__init__(status_code=404, detail=detail)


class UserAccessDeniedError(HTTPException):
    """The user does not have access to a given resource."""

    def __init__(self, detail: str = "The user does not have access to this resource"):
        super().__init__(status_code=403, detail=detail)


class InvalidUUIDError(HTTPException):
    """The provided UUID is invalid."""

    def __init__(self, detail: str = "The provided UUID is invalid"):
        super().__init__(status_code=400, detail=detail)


class NoSystemUserError(HTTPException):
    """There is no system user."""

    def __init__(self, detail: str = "No system user found"):
        super().__init__(status_code=500, detail=detail)


class MemoryNotFoundError(HTTPException):
    """A memory with the given ID was not found."""

    def __init__(self, detail: str = "A memory with the given ID was not found"):
        super().__init__(status_code=404, detail=detail)


class ScopedStorageNotFoundError(HTTPException):
    """A scoped storage with the given ID was not found."""

    def __init__(self, detail: str = "A scoped storage with the given ID was not found"):
        super().__init__(status_code=404, detail=detail)


class RunNotFoundError(HTTPException):
    """A run with the given ID was not found."""

    def __init__(self, detail: str = "A run with the given ID was not found"):
        super().__init__(status_code=404, detail=detail)


class RunStepNotFoundError(HTTPException):
    """A run step with the given ID was not found."""

    def __init__(self, detail: str = "A run step with the given ID was not found"):
        super().__init__(status_code=404, detail=detail)


class ReferenceIntegrityError(HTTPException):
    """A reference integrity error occurred."""

    def __init__(self, detail: str = "A reference integrity error occurred"):
        super().__init__(status_code=400, detail=detail)


class RecordAlreadyExistsError(HTTPException):
    """A record with the given ID already exists."""

    def __init__(self, detail: str = "A record with the given ID already exists"):
        super().__init__(status_code=409, detail=detail)
