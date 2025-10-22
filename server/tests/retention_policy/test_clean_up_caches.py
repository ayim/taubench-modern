from typing import TYPE_CHECKING

from server.tests.storage_fixtures import *  # noqa: F403

if TYPE_CHECKING:
    from agent_platform.server.storage.postgres import PostgresStorage
    from agent_platform.server.storage.sqlite import SQLiteStorage


async def test_cache_eviction_retention_policy(
    storage: "SQLiteStorage|PostgresStorage",
) -> None:
    """Helper function to test cache eviction by retention policy worker."""
    from agent_platform.core.configurations.quotas import QuotasService
    from agent_platform.server.data_retention_policy import retention_policy_worker

    small_key = "small_cache_key"
    small_data = b"a" * 10
    await storage.set_cache_entry(small_key, small_data, 1.0)

    medium_key = "medium_cache_key"
    medium_data = b"b" * 100
    await storage.set_cache_entry(medium_key, medium_data, 2.0)

    large_key = "large_cache_key"
    large_data = b"c" * 1000
    await storage.set_cache_entry(large_key, large_data, 3.0)

    assert await storage.get_cache_entry(small_key) is not None
    assert await storage.get_cache_entry(medium_key) is not None
    assert await storage.get_cache_entry(large_key) is not None

    max_cache_size_bytes = len(large_data) + 2

    quota_service = await QuotasService.get_instance()
    old_max_cache_size_bytes = quota_service.get_max_cache_size()
    await quota_service.set_max_cache_size(max_cache_size_bytes)
    try:
        await retention_policy_worker()

        remaining_entries = await storage.list_cached_entries()
        total_size = sum(entry.cache_size_in_bytes for entry in remaining_entries.values())
        assert total_size <= max_cache_size_bytes, (
            f"Cache size {total_size} exceeds limit {max_cache_size_bytes}"
        )
        assert len(remaining_entries) == 1, (
            f"Expected 1 cache entry to be remaining, but found {len(remaining_entries)} entries"
        )
        assert await storage.get_cache_entry(small_key) is None
        assert await storage.get_cache_entry(medium_key) is None
        assert await storage.get_cache_entry(large_key) is not None

    finally:
        await quota_service.set_max_cache_size(old_max_cache_size_bytes)
