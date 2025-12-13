import json

import pytest
from pydantic import BaseModel, Field

from agent_platform.server.cache import CacheKeyStrategy, ThreadFileCache
from agent_platform.server.file_manager import FileManagerService
from server.tests.storage.sample_model_creator import SampleModelCreator


class SampleCachedData(BaseModel):
    """Sample Pydantic model for testing."""

    value: str
    metadata: dict = Field(default_factory=dict)


class DataWithValidation(BaseModel):
    """Sample model with validation field."""

    content: str
    instructions: str


class SimpleCacheKeyStrategy(CacheKeyStrategy):
    """Simple cache key strategy using file_ref."""

    def generate_key(self, file_ref: str) -> str:
        """Generate cache key from file_ref."""
        return f"{file_ref}.cache.json"


class ValidatedCacheKeyStrategy(CacheKeyStrategy):
    """Cache key strategy for validated cache (ignores instructions in key)."""

    def generate_key(self, file_ref: str, instructions: str = "") -> str:
        """Generate cache key from file_ref only (instructions is ignored but accepted)."""
        return f"{file_ref}.validated.json"


@pytest.mark.asyncio
async def test_cache_miss_then_set_then_hit(sqlite_storage, sqlite_model_creator: SampleModelCreator):
    """Test basic cache workflow: miss, set, then hit."""
    # Setup
    storage = sqlite_storage
    file_manager = FileManagerService.get_instance(storage=storage)

    user_id = await sqlite_model_creator.get_user_id()
    thread = await sqlite_model_creator.obtain_sample_thread()

    cache = ThreadFileCache[SampleCachedData, ...](
        storage=storage,
        file_manager=file_manager,
        key_strategy=SimpleCacheKeyStrategy(),
        validate_fn=None,
    )

    # Test cache miss
    result = await cache.get(
        thread=thread,
        user_id=user_id,
        model_class=SampleCachedData,
        file_ref="test_file.pdf",
    )
    assert result is None

    # Test cache set
    data = SampleCachedData(value="test_value", metadata={"key": "value"})
    uploaded = await cache.set(
        thread=thread,
        user_id=user_id,
        data=data,
        file_ref="test_file.pdf",
    )
    assert uploaded.file_ref == "test_file.pdf.cache.json"

    # Test cache hit
    cached = await cache.get(
        thread=thread,
        user_id=user_id,
        model_class=SampleCachedData,
        file_ref="test_file.pdf",
    )
    assert cached is not None
    assert cached.value == "test_value"
    assert cached.metadata == {"key": "value"}

    # Verify the contents in the cache file are accurate.
    actual_cached_file = await storage.get_file_by_ref(thread, "test_file.pdf.cache.json", user_id)
    cached_file_contents = await file_manager.read_file_contents(actual_cached_file.file_id, user_id)
    cached_file_contents = json.loads(cached_file_contents)
    assert SampleCachedData.model_validate(cached_file_contents) == data


@pytest.mark.asyncio
async def test_cache_with_custom_validation(sqlite_storage, sqlite_model_creator: SampleModelCreator):
    """Test cache with custom validation logic."""
    # Setup
    storage = sqlite_storage
    file_manager = FileManagerService.get_instance(storage=storage)

    user_id = await sqlite_model_creator.get_user_id()
    thread = await sqlite_model_creator.obtain_sample_thread()

    # Cache with validation function that checks instructions match
    cache = ThreadFileCache[DataWithValidation, ...](
        storage=storage,
        file_manager=file_manager,
        key_strategy=ValidatedCacheKeyStrategy(),
        validate_fn=lambda cached, ctx: cached.instructions == ctx.get("instructions"),
    )

    # Store data with specific instructions
    data = DataWithValidation(content="extracted data", instructions="extract tables")
    await cache.set(
        thread=thread,
        user_id=user_id,
        data=data,
        file_ref="doc.pdf",
    )

    # Cache hit with matching instructions
    cached = await cache.get(
        thread=thread,
        user_id=user_id,
        model_class=DataWithValidation,
        file_ref="doc.pdf",
        instructions="extract tables",
    )
    assert cached is not None
    assert cached.content == "extracted data"
    assert cached.instructions == "extract tables"

    # Cache miss with different instructions (validation fails)
    cached = await cache.get(
        thread=thread,
        user_id=user_id,
        model_class=DataWithValidation,
        file_ref="doc.pdf",
        instructions="extract images",
    )
    assert cached is None


@pytest.mark.asyncio
async def test_multiple_cache_entries(sqlite_storage, sqlite_model_creator: SampleModelCreator):
    """Test storing and retrieving multiple cache entries."""
    # Setup
    storage = sqlite_storage
    file_manager = FileManagerService.get_instance(storage=storage)

    user_id = await sqlite_model_creator.get_user_id()
    thread = await sqlite_model_creator.obtain_sample_thread()

    cache = ThreadFileCache[SampleCachedData, ...](
        storage=storage,
        file_manager=file_manager,
        key_strategy=SimpleCacheKeyStrategy(),
        validate_fn=None,
    )

    # Store multiple entries
    data1 = SampleCachedData(value="first", metadata={"index": 1})
    data2 = SampleCachedData(value="second", metadata={"index": 2})
    data3 = SampleCachedData(value="third", metadata={"index": 3})

    await cache.set(thread, user_id, data1, file_ref="file1.pdf")
    await cache.set(thread, user_id, data2, file_ref="file2.pdf")
    await cache.set(thread, user_id, data3, file_ref="file3.pdf")

    # Retrieve all entries
    cached1 = await cache.get(thread, user_id, SampleCachedData, file_ref="file1.pdf")
    assert cached1 is not None
    assert cached1.value == "first"

    cached2 = await cache.get(thread, user_id, SampleCachedData, file_ref="file2.pdf")
    assert cached2 is not None
    assert cached2.value == "second"

    cached3 = await cache.get(thread, user_id, SampleCachedData, file_ref="file3.pdf")
    assert cached3 is not None
    assert cached3.value == "third"


@pytest.mark.asyncio
async def test_cache_pop(sqlite_storage, sqlite_model_creator: SampleModelCreator):
    """Test removing cache entries."""
    # Setup
    storage = sqlite_storage
    file_manager = FileManagerService.get_instance(storage=storage)
    user_id = await sqlite_model_creator.get_user_id()

    # Obtain sample thread
    thread = await sqlite_model_creator.obtain_sample_thread()

    cache = ThreadFileCache[SampleCachedData, ...](
        storage=storage,
        file_manager=file_manager,
        key_strategy=SimpleCacheKeyStrategy(),
        validate_fn=None,
    )

    # Store and verify
    data = SampleCachedData(value="to_be_removed")
    await cache.set(thread, user_id, data, file_ref="temp.pdf")
    cached = await cache.get(thread, user_id, SampleCachedData, file_ref="temp.pdf")
    assert cached is not None

    # Remove from cache
    removed = await cache.pop(thread, user_id, file_ref="temp.pdf")
    assert removed is True

    # Verify it's gone
    cached = await cache.get(thread, user_id, SampleCachedData, file_ref="temp.pdf")
    assert cached is None

    # Double pop should return False
    removed = await cache.pop(thread, user_id, file_ref="temp.pdf")
    assert removed is False
