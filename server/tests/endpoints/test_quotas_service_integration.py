import pytest
import sqlalchemy as sa

from agent_platform.core.configurations.config_validation import ConfigType
from agent_platform.core.configurations.quotas import QuotasService
from agent_platform.core.errors import PlatformHTTPError
from agent_platform.server.storage.option import StorageService


class TestQuotasServiceIntegration:
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
        # Note: this runs for both sqlite and postgres storage.
        # This is because we want to test the test the QuotasService functionality
        # and not whether the storage is actually able to apply the pool size.
        StorageService.set_for_testing(storage)
        QuotasService._instance = None

        quotas_service = await QuotasService.get_instance()

        # Default is 50 (from QuotasService mapping)
        assert quotas_service.get_postgres_pool_max_size() == 50

        # Set to a valid value
        await quotas_service.set_postgres_pool_max_size("80")
        assert quotas_service.get_postgres_pool_max_size() == 80

        # Persisted across instances
        QuotasService._instance = None
        fresh = await QuotasService.get_instance()
        assert fresh.get_postgres_pool_max_size() == 80

        # Invalid values are rejected
        for bad in ["0", "-1"]:
            with pytest.raises(PlatformHTTPError):
                await quotas_service.set_postgres_pool_max_size(bad)

    @pytest.mark.postgresql
    async def test_postgres_pool_size_applied_to_actual_pools(self, postgres_storage):
        """Verify that apply_pool_size() resizes both psycopg and SQLAlchemy pools."""
        # Use the fixture-provided storage (comes with clean schema per test)
        StorageService.set_for_testing(postgres_storage)
        QuotasService._instance = None

        quotas_service = await QuotasService.get_instance()

        # Get current pool size (fixture creates pool with max_size=50)
        initial_stats = postgres_storage._pool.get_stats()
        initial_max = initial_stats["pool_max"]
        assert initial_max == 50, f"Pool should start with default 50, got {initial_max}"

        # Now resize to a different value via API
        new_size = 100
        await quotas_service.set_config(ConfigType.POSTGRES_POOL_MAX_SIZE, str(new_size))

        # Verify psycopg pool was resized
        updated_stats = postgres_storage._pool.get_stats()
        assert updated_stats["pool_max"] == new_size, (
            f"psycopg pool not resized: expected {new_size}, got {updated_stats['pool_max']}"
        )

        # Pretty hacky check as the status() method returns a string with the pool size;
        # adding it for completeness.
        updated_stats_sa = postgres_storage._sa_engine.pool.status()
        assert f"Pool size: {new_size}" in updated_stats_sa, (
            f"SQLAlchemy pool not resized: expected {new_size}, got {updated_stats_sa}"
        )

        # Verify SQLAlchemy engine is functional after swap
        async with postgres_storage._sa_engine.begin() as conn:
            result = await conn.execute(sa.text("SELECT 1 as test_value"))
            row = result.fetchone()
            assert row is not None, "Query should return a row"
            assert row[0] == 1, "SQLAlchemy engine not functional after resize"

        # Verify psycopg pool is functional after resize
        async with postgres_storage._pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1 as test_value")
                row = await cur.fetchone()
                assert row is not None, "Query should return a row"
                assert row[0] == 1, "psycopg pool not functional after resize"


class TestQuotasEnvOverrides:
    async def test_env_var_takes_precedence_over_storage(self, storage, monkeypatch):
        # Ensure the test storage is used and singleton is reset
        StorageService.set_for_testing(storage)
        QuotasService._instance = None

        # Pre-populate storage with a value for MAX_AGENTS
        await StorageService.get_instance().set_config(ConfigType.MAX_AGENTS, "5")

        # Set env var override to a different value
        monkeypatch.setenv("SEMA4AI_AGENT_SERVER_MAX_AGENTS", "7")

        # Initialize quotas; env override should be applied and persisted
        quotas_service = await QuotasService.get_instance()
        assert quotas_service.get_max_agents() == 7

        # Reset and re-initialize to ensure value was persisted to storage
        QuotasService._instance = None
        quotas_service2 = await QuotasService.get_instance()
        assert quotas_service2.get_max_agents() == 7

        # Cleanup
        monkeypatch.delenv("SEMA4AI_AGENT_SERVER_MAX_AGENTS", raising=False)
        QuotasService._instance = None
        StorageService.reset()

    async def test_storage_value_used_when_no_env_var(self, storage):
        StorageService.set_for_testing(storage)
        QuotasService._instance = None

        # Pre-populate storage with a value for MAX_AGENTS
        await StorageService.get_instance().set_config(ConfigType.MAX_AGENTS, "12")

        quotas_service = await QuotasService.get_instance()
        assert quotas_service.get_max_agents() == 12

        QuotasService._instance = None
        StorageService.reset()

    async def test_default_used_when_no_env_or_storage(self, storage):
        StorageService.set_for_testing(storage)
        QuotasService._instance = None

        # Do not set any storage or env; should use default (100 for MAX_AGENTS)
        quotas_service = await QuotasService.get_instance()
        assert quotas_service.get_max_agents() == 100

        QuotasService._instance = None
        StorageService.reset()
