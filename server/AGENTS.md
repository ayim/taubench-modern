# Agent Platform Golden Rules

This document defines the key patterns, conventions, and best practices for the `agent-platform` Python codebase. Follow these rules when implementing new features to ensure consistency and maintainability.

---

## 1. Code Organization & Structure

### Directory Layout

- **Standard src/ layout**: Use `src/agent_platform/{core,server}/` structure
- **Module-per-domain**: Each major feature has its own directory (e.g., `agent/`, `platforms/`, `evals/`)
- **Test structure mirrors source**: Tests in separate `tests/` directory with same structure as `src/`

```
core/src/agent_platform/core/
├── agent/
├── platforms/
│   ├── openai/
│   ├── azure/
│   └── cortex/
├── errors/
└── configurations/

core/tests/
├── agent/
├── platforms/
└── ...
```

### Import Patterns

- **Use absolute imports**: `from agent_platform.core.errors import PlatformError`
- **Avoid doing re-exports in `__init__.py` and prefer to import from the module directly**
- **Use TYPE_CHECKING for symbols that are only used for type checking**

  ```python
  from typing import TYPE_CHECKING

  if TYPE_CHECKING:
      from agent_platform.server.storage.types import StaleThreadsResult
  ```

### Naming Conventions

| Element           | Convention         | Example                                    |
| ----------------- | ------------------ | ------------------------------------------ |
| Files             | `snake_case.py`    | `data_connections.py`, `error_handlers.py` |
| Classes           | `PascalCase`       | `PlatformError`, `DataFramesKernel`        |
| Functions/Methods | `snake_case`       | `setup_logging`, `compute_generic_deltas`  |
| Constants         | `UPPER_SNAKE_CASE` | `WORK_ITEMS_SYSTEM_USER_SUB`               |
| Private functions | Leading underscore | `_get_default_formatter()`                 |

---

## 2. Python Programming Patterns

### Error Handling

**Prefer to use PlatformHttpError** (error messages from those should be readable and
the related message is sent to the client - as such these messages should not contain sensitive information).
Subclasses from PlatformHttpError can be used for convenience to create custom error hierarchies.
Other hierarchies for internal errors should inherit from `PlatformError`.

**Simple error pattern for smaller modules:**

```python
class ConfigurationError(PlatformHttpError):
    """Base class for all configuration errors."""

class ConfigurationDiscriminatorError(ConfigurationError):
    """Error raised when there is a mismatch between discriminator values."""
```

### Async/Await Patterns

- **Async by default** for I/O operations
- **Use async context managers** for resource management
  ```python
  @asynccontextmanager
  async def _write_connection(self) -> AsyncIterator[AsyncConnection]:
      """Acquire write lock and open transactional connection."""
      async with self._write_lock:
          async with self._sa_engine.begin() as conn:
              yield conn
  ```
- **Define protocols for async resources**:
  ```python
  @runtime_checkable
  class AsyncLockLike(Protocol):
      """API for async-io lock which can only be used as context manager."""
      async def __aenter__(self) -> "AsyncLockLike": ...
      async def __aexit__(...) -> bool | None: ...
  ```

### Type Hints & Annotations

**Very strict typing throughout:**

- **Union types using `|` syntax**
  ```python
  merged_credentials: dict | None
  user_id: str
  ```
- **Literal types** for enums and constants
  ```python
  db_type: Literal["sqlite", "postgres"] = field(default="sqlite")
  ```
- **Generic types when helpful**
  ```python
  def combine_generic_deltas(deltas: list[GenericDelta]) -> list[GenericDelta]:
  ```
- **Always include return type annotations**
- **Avoid `Any` unless absolutely necessary**

### Dataclasses vs Pydantic

**Frozen dataclasses for core domain models:**

```python
@dataclass(frozen=True)
class User:
    _parsed_sub: dict[str, str] | None = field(default=None, init=False, repr=False)
    user_id: str = field(metadata={"description": "The user's unique identifier."})
    sub: str = field(metadata={"description": "The user's sub (from a JWT token)."})
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
```

**Pydantic for validation & serialization:**

```python
from pydantic import BaseModel, Field

class StatusError(BaseModel):
    code: str
    message: str
```

**Manual serialization methods on dataclasses:**

```python
def model_dump(self) -> dict:
    """Convert to dictionary."""
    return {
        "user_id": self.user_id,
        "created_at": self.created_at.isoformat(),
    }

@classmethod
def model_validate(cls, data: dict) -> "User":
    """Create from dictionary."""
    data = data.copy()
    if "created_at" in data and isinstance(data["created_at"], str):
        data["created_at"] = datetime.fromisoformat(data["created_at"])
    return cls(**data)
```

### Function vs Class Preferences

- **Functions preferred** for stateless operations
- **Use classes when**:

  - State persistence needed
  - Complex initialization required
  - Defining protocols with abstract base classes

  ```python
  class BaseStorage(AbstractStorage, CommonMixin):
      """Base class for storage backends."""

      _write_lock: AsyncLockLike  # Subclasses must set this

      def __init__(self):
          super().__init__()
          self.__sa_engine: AsyncEngine | None = None
  ```

### Decorator Usage

- `@dataclass` and `@dataclass(frozen=True)` for data structures
- `@abstractmethod` for abstract base classes
- `@property` for computed attributes
- `@classmethod` for alternative constructors
- `@asynccontextmanager` for async resource management
- `@runtime_checkable` with Protocol classes

---

## 3. Testing Practices

### Test Structure

- **Pytest exclusively** for testing framework
- **Test files**: `test_*.py` naming (e.g., `test_generic_delta.py`)
- **Test location**: Mirrors source structure in separate `tests/` directory
- **Whenever possible don't use mocks or dummy data**. Example: to create a test
  don't use a dummy storage with dummy created data, prefer to use the real sqlite storage
  with `SampleModelCreator` to create real data and then test the code with that data.
  -- the postgres storage should be used for storage tests itself, but for testing other
  behaviors in the platform, usually testing with the sqlite storage is enough.

### Fixtures Pattern

```python
# tests/conftest.py
@pytest.fixture(autouse=True)
def _clear_http_proxy_env(monkeypatch):
    """Remove HTTP proxy environment variables."""
    proxy_vars = ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]
    for var in proxy_vars:
        monkeypatch.delenv(var, raising=False)
```

### Test Organization

```python
def test_generic_delta_init_and_dict():
    """Basic test to ensure GenericDelta can be constructed."""
    delta = GenericDelta(op="replace", path="/foo/bar", value="new_value")
    assert delta.op == "replace"

@pytest.mark.parametrize(
    ("op", "path", "value", "from_", "expected_error", "error_match"),
    [
        ("add", "/test", "test", None, None, None),
        ("remove", "invalid", NO_VALUE, None, InvalidPathError, "Invalid target path"),
    ],
    ids=["valid-simple-path", "invalid-character-sequence"],
)
def test_path_validation(op, path, value, from_, expected_error, error_match):
    """Test path validation."""
    if expected_error:
        with pytest.raises(expected_error, match=error_match):
            GenericDelta(op=op, path=path, value=value, from_=from_)
    else:
        delta = GenericDelta(op=op, path=path, value=value, from_=from_)
        assert delta is not None
```

### FastAPI Test Fixtures

```python
@pytest.fixture
def fastapi_app(sqlite_storage: "SQLiteStorage", stub_user) -> FastAPI:
    StorageService.reset()
    StorageService.set_for_testing(storage)

    app = FastAPI()
    app.include_router(work_items_public, prefix="/api/public/v1/work-items")
    app.dependency_overrides[auth_user] = lambda: stub_user
    add_exception_handlers(app)
    return app

@pytest.fixture
def client(fastapi_app: FastAPI) -> TestClient:
    return TestClient(fastapi_app)
```

---

## 4. Type Safety & Validation

### Type Hint Strictness

- **Avoid casting** where possible
- **Use `cast()` sparingly** and document why
  ```python
  from typing import cast
  stored_platform = await storage.get_platform_params(platform_params.platform_id)
  return cast(AnyPlatformParameters, stored_platform)
  ```

### Optional vs None Handling

- **Explicit `None` in unions**: `str | None` preferred over `Optional[str]`
- **Default None for optional parameters**
  ```python
  def __init__(
      self,
      error_code: ErrorCode = ErrorCode.UNEXPECTED,
      message: str | None = None,
      data: dict[str, Any] | None = None,
  ) -> None:
  ```

### Protocol/ABC Usage

```python
from abc import abstractmethod
from typing import Protocol, runtime_checkable

@runtime_checkable
class AsyncLockLike(Protocol):
    """API for an async-io lock."""
    async def __aenter__(self) -> "AsyncLockLike": ...
    async def __aexit__(...) -> bool | None: ...
```

---

## 5. Documentation

### Docstring Style

**Use Google-style docstrings** with comprehensive module-level docs:

```python
"""Platform error system with automatic structured logging integration.

This module defines a hierarchy of exception classes designed to work seamlessly with
FastAPI and structlog for rich, structured error logging and handling.

Architecture Overview:
    The error system provides:
    - Automatic unique error IDs (UUIDs) for tracing
    - Structured context data that integrates with structlog
    - FastAPI-compatible HTTP and WebSocket exceptions

Example:
    raise PlatformError(
        ErrorCode.UNEXPECTED,
        "Configuration validation failed",
        data={"config_key": "database_url"}
    )
"""
```

**Function/method docstrings:**

```python
def setup_logging(default_mode: bool = False, log_level: str | None = None):
    """Set up logging configuration.

    Args:
        default_mode: If True, use environment variables for minimal setup.
                     If False, use full system configuration.
        log_level: The log level to use. If None, tries to use environment
                   variable SEMA4AI_AGENT_SERVER_LOG_LEVEL or defaults to
                   "INFO".
    """
```

### Inline Comments

- **Minimal inline comments** - code should be self-documenting
- **Use for complex logic explanation**
  ```python
  # Dataclass is frozen, so we need to use
  # special syntax to set the _parsed_sub field
  object.__setattr__(self, "_parsed_sub", self._parse_sub(self.sub))
  ```

---

## 6. Dependencies & Configuration

### pyproject.toml Structure

```toml
[project]
name = "agent_platform_core"
version = "2.0.0"
requires-python = ">=3.12"
authors = [{ name = "Sema4.ai Engineering", email = "engineering@sema4.ai" }]

dependencies = [
    "jsonpatch>=1.33,<2.0.0",
    "mcp>=1.13.1,<2.0.0",
]

[project.optional-dependencies]
image-support = ["pillow>=11.3.0,<12.0.0"]
platforms-openai = ["openai>=1.106.0,<2.0.0"]

[tool.hatch.build.targets.wheel]
packages = ["src/agent_platform"]
```

### Version Pinning Strategy

- **Major version constrained**: `>=X.Y.Z,<X+1.0.0`
- **Specific versions for critical deps**: `sema4ai-common==0.1.0`

### Configuration via Dataclasses

```python
@dataclass(frozen=True)
class SystemConfig(Configuration):
    """System-wide configuration settings."""

    name: str = field(
        default="Agent Server",
        metadata=FieldMetadata(
            description="The name of the agent server.",
            env_vars=["SEMA4AI_AGENT_SERVER_NAME"],
        ),
    )

    db_type: Literal["sqlite", "postgres"] = field(
        default="sqlite",
        metadata=FieldMetadata(
            description="The type of database to use.",
            env_vars=["SEMA4AI_AGENT_SERVER_DB_TYPE", "DB_TYPE"],
        ),
    )
```

---

## 7. API/Interface Design

### FastAPI Patterns

**Type-safe endpoint definitions:**

```python
from fastapi import APIRouter

router = APIRouter()

@router.post("/", response_model=AnyPlatformParameters)
async def create_platform(
    payload: UpsertPlatformConfigPayload,
    user: AuthedUser,
    storage: StorageDependency,
) -> AnyPlatformParameters:
    """Create a new platform configuration."""
    platform_params = payload.to_platform_parameters()
    await storage.create_platform_params(platform_params)
    stored_platform = await storage.get_platform_params(platform_params.platform_id)
    return cast(AnyPlatformParameters, stored_platform)

@router.delete("/{platform_id}", status_code=204)
async def delete_platform(
    platform_id: str,
    user: AuthedUser,
    storage: StorageDependency,
) -> None:
    """Delete a platform configuration."""
    await storage.delete_platform_params(platform_id)
```

### Payload Pattern

**Dataclass-based payloads** for request/response:

```python
@dataclass
class CreateWorkItemPayload:
    """Payload for creating a work item."""

    agent_id: str = field(
        metadata={"description": "The ID of the agent."},
    )

    messages: list[ThreadMessage] = field(
        default_factory=list,
        metadata={"description": "The messages in the work item."},
    )

    @classmethod
    def to_work_item(
        cls,
        payload: "CreateWorkItemPayload",
        owner_user_id: str,
        created_by_user_id: str,
    ) -> WorkItem:
        """Convert payload to WorkItem."""
        work_item_id = payload.work_item_id or str(uuid4())
        return WorkItem(...)
```

### Dependency Injection

```python
from typing import Annotated
from fastapi import Depends

StorageDependency = Annotated[AbstractStorage, Depends(get_storage)]
AuthedUser = Annotated[User, Depends(auth_user)]
```

---

## 8. Logging & Monitoring

### Logging Setup

**Use structlog with custom processors:**

```python
import structlog

def _platform_error_processor(logger, method_name, event_dict):
    """Extract error_id from PlatformError exceptions."""
    exc_info = event_dict.get("exc_info")
    if exc_info and isinstance(exc_info, PlatformError):
        error_id = exc_info.response.error_id
        current_event = event_dict.get("event", "")
        event_dict["event"] = f"{current_event} (error_id={error_id})"
    return event_dict

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        _platform_error_processor,
    ],
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
)
```

### Logger Usage

```python
import structlog

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

logger.info("Processing request", user_id=user_id, request_id=request_id)
logger.error("Failed to process", exc_info=True)
```

### Error ID Tracking

Every error includes a UUID for tracing:

```python
error_response = ErrorResponse(error_code, message_override=user_message)
logger.error(f"{log_message} (error_id={error_response.error_id})")
```

---

## 9. Code Quality Standards

### Import Ordering

Standard Python import order:

1. Standard library
2. Third-party packages
3. Local application imports

```python
import json
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any, Literal

from fastapi import Request
from opentelemetry import metrics, trace

from agent_platform.core.user import User
from agent_platform.core.errors import PlatformError
```

### Code Formatting

- Code wraps around 100 characters generally
- Consistent style (likely black or ruff)

---

## 10. Additional Key Patterns

### Context Pattern

**Use context objects for dependency injection:**

```python
@dataclass
class UserContext:
    """User context information."""
    user: User
    profile: dict[str, Any]

class LangSmithContext:
    """LangSmith context information and operations."""
    def __init__(self, server_context: "AgentServerContext", config: ObservabilityConfig | None):
        self.config = config
        self.server_context = server_context
```

### Metadata Fields Pattern

```python
user_id: str = field(
    metadata={
        "description": "The user's unique identifier.",
        "env_vars": ["SEMA4AI_AGENT_SERVER_NAME"]
    }
)
```

### UTC Datetime Defaults

```python
from datetime import UTC, datetime

created_at: datetime = field(
    default_factory=lambda: datetime.now(UTC)
)
```

### Private Helper Functions

Functions prefixed with `_` are module-private:

```python
def _normalized_path(path: str | Path) -> Path:
    return Path(os.path.normpath(os.path.abspath(path)))

def _hyphenated_name(name: str) -> str:
    return name.lower().replace(" ", "-")
```

---

## Summary: Key Differentiators

1. **Frozen dataclasses** over Pydantic for core domain models
2. **Explicit serialization methods** (`model_dump`, `model_validate`) on dataclasses
3. **Hierarchical error system** with UUID tracking and structured logging
4. **Async-first** with extensive use of async context managers
5. **Type safety is paramount** - minimal use of `Any`, explicit `None` in unions
6. **Metadata-driven configuration** with environment variable support
7. **Pytest with class-based test organization** and extensive fixtures
8. **Structlog for structured logging** with custom processors
9. **Protocol classes** for defining interfaces
10. **Absolute imports** with explicit `__all__` exports

---

## Quick Checklist for New Code

- [ ] Use frozen dataclasses for immutable domain models
- [ ] Include comprehensive type hints (no `Any`)
- [ ] Add Google-style docstrings for public APIs
- [ ] Use absolute imports
- [ ] Add `__all__` to `__init__.py` files
- [ ] Make I/O operations async
- [ ] Use hierarchical exceptions with error IDs
- [ ] Include metadata in field definitions
- [ ] Write pytest tests that mirror source structure
- [ ] Use structlog for logging with context
- [ ] Follow snake_case for functions, PascalCase for classes
- [ ] Pin dependencies with major version constraints
- [ ] Prefer `str | None` over `Optional[str]`
- [ ] Use `datetime.now(UTC)` for timestamps
- [ ] Add type annotations to all function signatures
