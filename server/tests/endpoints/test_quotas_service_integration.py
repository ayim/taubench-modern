import pytest
import sqlalchemy as sa

from agent_platform.core.configurations.config_validation import ConfigType
from agent_platform.core.configurations.quotas import QuotasService
from agent_platform.core.errors import PlatformHTTPError
from agent_platform.server.storage.option import StorageService
from agent_platform.server.storage.postgres import PostgresStorage


class TestQuotasServiceIntegration:
    async def test_set_and_get_max_parallel_work_items_round_trip(self, storage):
        StorageService.set_for_testing(storage)
        QuotasService._instance = None

        quotas_service = await QuotasService.get_instance()
        default_value = quotas_service.get_max_parallel_work_items_in_process()
        assert default_value == 10

        new_value = "25"
        await quotas_service.set_max_parallel_work_items_in_process(new_value)

        current_value = quotas_service.get_max_parallel_work_items_in_process()
        assert current_value == 25

        QuotasService._instance = None
        fresh_quotas_service = await QuotasService.get_instance()
        persisted_value = fresh_quotas_service.get_max_parallel_work_items_in_process()

        assert persisted_value == 25

    async def test_background_worker_uses_updated_quota_value(self, storage):
        StorageService.set_for_testing(storage)
        QuotasService._instance = None

        quotas_service = await QuotasService.get_instance()
        await quotas_service.set_max_parallel_work_items_in_process("15")

        worker_quotas_service = await QuotasService.get_instance()
        max_batch_size = worker_quotas_service.get_max_parallel_work_items_in_process()

        assert max_batch_size == 15

    async def test_regression__initialize_from_storage(self, storage):
        StorageService.set_for_testing(storage)
        await StorageService.get_instance().set_config(QuotasService.MAX_AGENTS, {"current": "99"})

        QuotasService._instance = None

        quotas_service = await QuotasService.get_instance()
        assert quotas_service.get_max_agents() == 99

    def teardown_method(self):
        QuotasService._instance = None
        StorageService.reset()

    async def test_postgres_pool_max_size_round_trip_and_validation(self, storage):
        StorageService.set_for_testing(storage)
        QuotasService._instance = None

        quotas_service = await QuotasService.get_instance()

        # Default is 50 (from QuotasService mapping)
        assert quotas_service.get_config(ConfigType.POSTGRES_POOL_MAX_SIZE) == 50

        # Set to a valid value
        await quotas_service.set_config(ConfigType.POSTGRES_POOL_MAX_SIZE, "80")
        assert quotas_service.get_config(ConfigType.POSTGRES_POOL_MAX_SIZE) == 80

        # Persisted across instances
        QuotasService._instance = None
        fresh = await QuotasService.get_instance()
        assert fresh.get_config(ConfigType.POSTGRES_POOL_MAX_SIZE) == 80

        # Invalid values are rejected
        for bad in ["0", "-1"]:
            with pytest.raises(PlatformHTTPError):
                await quotas_service.set_config(ConfigType.POSTGRES_POOL_MAX_SIZE, bad)

    @pytest.mark.postgresql
    async def test_postgres_pool_size_applied_to_actual_pools(self, postgres_testing):
        """Verify that PostgresStorage creates pool with configured size on startup."""
        dsn = postgres_testing.url()
        storage = PostgresStorage(dsn=dsn)

        try:
            # Setup will create pool with PostgresConfig.pool_max_size (default 50)
            await storage.setup()

            # Verify pools were created
            assert storage._pool is not None, "psycopg pool should be created"
            assert storage._sa_engine is not None, "SQLAlchemy engine should be created"

            # Set storage for QuotasService to use
            StorageService.set_for_testing(storage)
            quotas_service = await QuotasService.get_instance()

            # Get initial pool stats - should use PostgresConfig.pool_max_size default (50)
            initial_stats = storage._pool.get_stats()
            initial_max = initial_stats["pool_max"]
            assert initial_max == 50, f"Pool should start with default 50, got {initial_max}"

            # Now resize to a different value via API
            new_size = 100
            await quotas_service.set_config(ConfigType.POSTGRES_POOL_MAX_SIZE, str(new_size))

            # Verify psycopg pool was resized
            updated_stats = storage._pool.get_stats()
            assert updated_stats["pool_max"] == new_size, (
                f"psycopg pool not resized: expected {new_size}, got {updated_stats['pool_max']}"
            )

            # Pretty hacky check as the status() method returns a string with the pool size;
            # adding it for completeness.
            updated_stats_sa = storage._sa_engine.pool.status()
            assert f"Pool size: {new_size}" in updated_stats_sa, (
                f"SQLAlchemy pool not resized: expected {new_size}, got {updated_stats_sa}"
            )

            # Verify SQLAlchemy engine is functional after swap
            async with storage._sa_engine.begin() as conn:
                result = await conn.execute(sa.text("SELECT 1 as test_value"))
                row = result.fetchone()
                assert row is not None, "Query should return a row"
                assert row[0] == 1, "SQLAlchemy engine not functional after resize"

            # Verify psycopg pool is functional after resize
            async with storage._pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute("SELECT 1 as test_value")
                    row = await cur.fetchone()
                    assert row is not None, "Query should return a row"
                    assert row[0] == 1, "psycopg pool not functional after resize"
        finally:
            # Clean up
            await storage.teardown()
            StorageService.reset()
            QuotasService._instance = None
