import typing

import pytest

if typing.TYPE_CHECKING:
    from agent_platform.server.storage.postgres import PostgresStorage
    from agent_platform.server.storage.sqlite import SQLiteStorage


@pytest.mark.asyncio
async def test_cache_storage_crud(
    storage: "SQLiteStorage|PostgresStorage",
) -> None:
    """Test cache storage CRUD operations."""
    # Test setting a cache entry
    cache_key = "test_cache_key"
    cache_data = b"test cache data"
    time_to_compute = 1.5

    await storage.set_cache_entry(cache_key, b"to be overwritten", time_to_compute)
    # Set the same cache again to test that it overwrites the existing entry
    await storage.set_cache_entry(cache_key, cache_data, time_to_compute)

    # Test getting the cache entry
    result = await storage.get_cache_entry(cache_key)
    assert result is not None
    assert result.cache_data == cache_data
    assert result.time_to_compute_data_in_seconds == time_to_compute
    assert result.cache_size_in_bytes == len(cache_data)

    # Test getting non-existent cache entry
    non_existent_key = "non_existent_key"
    result = await storage.get_cache_entry(non_existent_key)
    assert result is None

    # Test setting multiple cache entries
    cache_key_2 = "test_cache_key_2"
    cache_data_2 = b"test cache data 2"
    time_to_compute_2 = 2.0

    await storage.set_cache_entry(cache_key_2, cache_data_2, time_to_compute_2)

    # Verify both entries exist
    result_1 = await storage.get_cache_entry(cache_key)
    result_2 = await storage.get_cache_entry(cache_key_2)

    assert result_1 is not None
    assert result_2 is not None
    assert result_1.cache_data == cache_data
    assert result_2.cache_data == cache_data_2

    # Test cache eviction
    # Should only evict the first one
    await storage.evict_old_cache_entries_by_size(len(cache_data_2))

    result_1_after_eviction = await storage.get_cache_entry(cache_key)
    result_2_after_eviction = await storage.get_cache_entry(cache_key_2)

    assert result_1_after_eviction is None
    assert result_2_after_eviction is not None


@pytest.mark.asyncio
async def test_cache_storage_date_eviction(
    storage: "SQLiteStorage|PostgresStorage",
) -> None:
    """Test cache storage date-based eviction operations."""
    import datetime

    # Create cache entries with different ages
    # Entry 1: Very old (35 days ago)
    old_cache_key = "old_cache_key"
    old_cache_data = b"old cache data"
    old_time_to_compute = 1.0

    # We need to manually set the last_accessed_at to simulate an old entry
    old_date = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=35)
    await storage.set_cache_entry(
        old_cache_key, old_cache_data, old_time_to_compute, last_accessed_at=old_date
    )

    # Entry 2: Recent (1 day ago) - we'll simulate this by creating it normally
    recent_cache_key = "recent_cache_key"
    recent_cache_data = b"recent cache data"
    recent_time_to_compute = 2.0

    recent_date = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1)
    await storage.set_cache_entry(
        recent_cache_key, recent_cache_data, recent_time_to_compute, last_accessed_at=recent_date
    )

    # Note: we cannot "get" the entries with regular APIs as it'd update the last_accessed_at!
    list_entries = await storage.list_cached_entries()
    assert len(list_entries) == 2

    # Test with a very large max_age_days (should not evict anything)
    await storage.evict_old_cache_entries_by_date(max_age_days=365)

    list_entries = await storage.list_cached_entries()
    assert len(list_entries) == 2

    # Test just prunning the "old"
    await storage.evict_old_cache_entries_by_date(max_age_days=20)

    list_entries = await storage.list_cached_entries()
    assert len(list_entries) == 1
    for cache_key, entry in list_entries.items():
        assert cache_key == recent_cache_key
        assert entry.cache_size_in_bytes == len(recent_cache_data)

    # Test just prunning all
    await storage.evict_old_cache_entries_by_date(max_age_days=0)

    list_entries = await storage.list_cached_entries()
    assert len(list_entries) == 0
