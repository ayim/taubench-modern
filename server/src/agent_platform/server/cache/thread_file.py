"""General-purpose thread file storage cache for arbitrary Pydantic models.

This module provides a generic cache implementation that stores Pydantic models as JSON
files in thread file storage. The API is inspired by Python's collections.abc.MutableMapping
but uses async methods since storage operations must be async.

We cannot directly inherit from MutableMapping because it requires
synchronous methods (__getitem__, __setitem__, etc.), but our storage and file operations
require async/await. Instead, we provide an async dict-like API (get, set, pop). Pop is
implemented but does not return the value that was removed.

The cache uses a Strategy Pattern with ABC to enforce type-safe cache key generation.
Each cache instance requires a CacheKeyStrategy that defines the exact signature of
parameters needed for generating cache keys.
"""

import io
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, Generic, ParamSpec, TypeVar

import structlog
from pydantic import BaseModel

from agent_platform.core.files import UploadedFile
from agent_platform.core.payloads import UploadFilePayload
from agent_platform.core.thread import Thread
from agent_platform.server.storage import BaseStorage

if TYPE_CHECKING:
    from agent_platform.server.file_manager.base import BaseFileManager

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)
P = ParamSpec("P")


class CacheKeyStrategy(ABC, Generic[P]):
    """Abstract base class for cache key generation strategies.

    Subclasses must implement the generate_key method with their specific parameter
    signature, which is captured by the ParamSpec P.

    The use of ParamSpec ensures type safety: the ThreadFileCache.get() and set()
    methods will be type-checked to ensure callers provide the exact parameters
    required by the strategy's generate_key() signature.

    Example:
        ```python
        class SchemaCacheKeyStrategy(CacheKeyStrategy):
            def generate_key(self, file_ref: str) -> str:
                return f"{file_ref}.schema.json"

        cache = ThreadFileCache(
            storage=storage,
            file_manager=file_manager,
            key_strategy=SchemaCacheKeyStrategy(),
        )

        # Type-safe: linter knows file_ref is required
        await cache.get(thread, user_id, Model, file_ref="doc.pdf")
        ```
    """

    @abstractmethod
    def generate_key(self, *args: P.args, **kwargs: P.kwargs) -> str:
        """Generate a cache key from the provided parameters. This string
        should be unique for the value being cached and should be human-readable
        (as it is shown to the user via the list of files in the thread).

        Subclasses must implement this method with their specific signature.
        The signature defines what parameters are required when using the cache.

        Returns:
            A string to use as the cache file name
        """


class ThreadFileCache(Generic[T, P]):
    """Async MutableMapping-inspired cache for Pydantic models in thread file storage.

    This cache stores Pydantic models as JSON files in thread file storage, providing
    a familiar dict-like API with async methods with type-safe cache key generation.

    Type Parameters:
        T: The Pydantic model type to cache
        P: ParamSpec capturing the signature of the cache key strategy

    Args:
        storage: Storage instance for accessing thread files
        file_manager: File manager for reading/writing file contents
        key_strategy: Strategy instance that generates cache file names
        validate_fn: Optional callable to check if cached data is still valid

    Example:
        ```python
        class SchemaCacheKeyStrategy(CacheKeyStrategy):
            def generate_key(self, file_ref: str) -> str:
                return f"{file_ref}.schema.json"

        cache = ThreadFileCache[SchemaModel, ...](
            storage=storage,
            file_manager=file_manager,
            key_strategy=SchemaCacheKeyStrategy(),
            validate_fn=lambda cached, ctx: cached.instructions == ctx.get("instructions")
        )

        # Type-safe: linter knows file_ref is required
        result = await cache.get(thread, user_id, SchemaModel, file_ref="doc.pdf")

        # Store in cache
        await cache.set(thread, user_id, schema_obj, file_ref="doc.pdf")
        ```
    """

    def __init__(
        self,
        storage: BaseStorage,
        file_manager: "BaseFileManager",
        key_strategy: CacheKeyStrategy[P],
        validate_fn: Callable[[T, dict[str, Any]], bool] | None = None,
    ):
        """Initialize the cache.

        Args:
            storage: Storage instance for accessing thread files
            file_manager: File manager for reading/writing file contents
            key_strategy: Strategy instance to generate cache file names
            validate_fn: Optional function to validate cached data with (model, context_dict)
        """
        self._storage = storage
        self._file_manager = file_manager
        self._key_strategy = key_strategy
        self._validate_fn = validate_fn

    async def get(
        self,
        thread: Thread,
        user_id: str,
        model_class: type[T],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T | None:
        """Get a cached value from thread file storage.

        This method attempts to load a cached Pydantic model from thread file storage.
        If a validate_fn was provided, it will be called to check if the cached data
        is still valid for the given parameters.

        Args:
            thread: Thread to load cache from
            user_id: User ID for access control
            model_class: Pydantic model class to deserialize into
            *args: Positional arguments passed to key strategy
            **kwargs: Keyword arguments passed to key strategy and validate_fn

        Returns:
            The cached model instance if found and valid, None otherwise
        """
        # Generate cache key using strategy
        cache_file_name = self._key_strategy.generate_key(*args, **kwargs)

        # Try to load the cached file
        cached_file = await self._storage.get_file_by_ref(thread, cache_file_name, user_id)
        if not cached_file:
            return None

        try:
            # Read and parse the cached data
            file_contents = await self._file_manager.read_file_contents(
                cached_file.file_id, user_id
            )
            cached_model = model_class.model_validate_json(file_contents)

            # Validate if validation function provided
            if self._validate_fn is not None:
                if not self._validate_fn(cached_model, kwargs):
                    logger.debug(
                        f"Cache validation failed for {cache_file_name}",
                        cache_file=cache_file_name,
                    )
                    return None

            logger.debug(f"Cache hit for {cache_file_name}", cache_file=cache_file_name)
            return cached_model

        except Exception as e:
            # We are likely to mask real bugs here, but the lower file service layers
            # don't return named exceptions for the "not found" case.
            logger.warning(
                f"Failed to load cached data from {cache_file_name}: {e!s}",
                cache_file=cache_file_name,
                error=str(e),
            )
            return None

    async def set(
        self,
        thread: Thread,
        user_id: str,
        data: T,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> UploadedFile:
        """Store a value in thread file storage cache.

        Args:
            thread: Thread to store cache in
            user_id: User ID for access control
            data: Pydantic model to cache
            *args: Positional arguments passed to key strategy
            **kwargs: Keyword arguments passed to key strategy

        Returns:
            UploadedFile metadata for the cached file
        """
        from fastapi import UploadFile

        # Generate cache key using strategy
        cache_file_name = self._key_strategy.generate_key(*args, **kwargs)

        # Serialize the data
        cache_json = data.model_dump_json()
        cache_file = UploadFile(
            filename=cache_file_name,
            file=io.BytesIO(cache_json.encode()),
        )

        # Upload to thread storage
        uploaded_files = await self._file_manager.upload(
            [UploadFilePayload(file=cache_file)], thread, user_id
        )

        logger.debug(f"Cache set for {cache_file_name}", cache_file=cache_file_name)
        return uploaded_files[0]

    async def pop(
        self,
        thread: Thread,
        user_id: str,
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> bool:
        """Removes a cached value from thread file storage.

        Args:
            thread: Thread to remove cache from
            user_id: User ID for access control
            *args: Positional arguments passed to key strategy
            **kwargs: Keyword arguments passed to key strategy

        Returns:
            True if a cached value was removed, else False
        """
        # Generate cache key using strategy
        cache_file_name = self._key_strategy.generate_key(*args, **kwargs)

        # Try to get the file
        cached_file = await self._storage.get_file_by_ref(thread, cache_file_name, user_id)
        if cached_file:
            await self._file_manager.delete(thread.thread_id, user_id, cached_file.file_id)
            logger.debug(f"Cache removed for {cache_file_name}", cache_file=cache_file_name)
            return True

        return False
