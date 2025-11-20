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

    async def test_work_item_timeout_seconds_get_set(self, storage):
        """Test that work_item_timeout_seconds can be get/set via QuotasService."""
        StorageService.set_for_testing(storage)
        QuotasService._instance = None

        quotas_service = await QuotasService.get_instance()

        # Default is 3600 (1 hour in seconds)
        assert quotas_service.get_work_item_timeout_seconds() == 3600

        # Set to a valid value
        await quotas_service.set_work_item_timeout_seconds("3601")
        assert quotas_service.get_work_item_timeout_seconds() == 3601

        # Persisted across instances
        QuotasService._instance = None
        fresh = await QuotasService.get_instance()
        assert fresh.get_work_item_timeout_seconds() == 3601

        # Invalid values are rejected
        for bad in ["-1", "not_a_number"]:
            with pytest.raises(PlatformHTTPError):
                await quotas_service.set_work_item_timeout_seconds(bad)

        # Zero is valid (edge case - no timeout)
        await quotas_service.set_work_item_timeout_seconds("0")
        assert quotas_service.get_work_item_timeout_seconds() == 0

        QuotasService._instance = None
        StorageService.reset()


class TestParallelWorkItemsValidation:
    """Test validation of PARALLEL_WORK_ITEMS constraint with POSTGRES_POOL_MAX_SIZE."""

    def teardown_method(self):
        QuotasService._instance = None
        StorageService.reset()

    async def test_set_parallel_work_items_to_invalid_value(self, storage):
        """Test setting PARALLEL_WORK_ITEMS above 80% of POSTGRES_POOL_MAX_SIZE fails."""
        StorageService.set_for_testing(storage)
        QuotasService._instance = None

        quotas_service = await QuotasService.get_instance()

        # Default POSTGRES_POOL_MAX_SIZE is 50, so 80% = 40
        # Attempting to set PARALLEL_WORK_ITEMS to 41 should fail
        with pytest.raises(PlatformHTTPError) as exc_info:
            await quotas_service.set_max_parallel_work_items_in_process("41")

        # Verify error details
        from agent_platform.core.errors.responses import ErrorCode

        error = exc_info.value
        assert error.response.error_code is ErrorCode.BAD_REQUEST
        assert "PARALLEL_WORK_ITEMS (41) cannot exceed 80%" in error.detail
        assert "POSTGRES_POOL_MAX_SIZE (50)" in error.detail
        assert "Maximum allowed: 40" in error.detail

        # Verify error data payload
        assert error.data["parallel_work_items"] == 41
        assert error.data["postgres_pool_max_size"] == 50
        assert error.data["max_allowed_parallel_work_items"] == 40
        assert "constraint" in error.data

        # Attempting to set PARALLEL_WORK_ITEMS to 0 (invalid value) should fail
        with pytest.raises(PlatformHTTPError) as exc_info:
            await quotas_service.set_max_parallel_work_items_in_process("0")

        # Verify error details
        error = exc_info.value
        assert error.response.error_code is ErrorCode.BAD_REQUEST
        assert "Invalid value 0 for MAX_PARALLEL_WORK_ITEMS_IN_PROCESS" in error.detail

    async def test_set_parallel_work_items_to_valid_value(self, storage):
        """Test setting PARALLEL_WORK_ITEMS at or below 80% succeeds."""
        StorageService.set_for_testing(storage)
        QuotasService._instance = None

        quotas_service = await QuotasService.get_instance()

        # Default POSTGRES_POOL_MAX_SIZE is 50, so 80% = 40
        # Setting to exactly 40 should succeed
        await quotas_service.set_max_parallel_work_items_in_process("40")
        assert quotas_service.get_max_parallel_work_items_in_process() == 40

        # Setting to 39 (below 80%) should also succeed
        await quotas_service.set_max_parallel_work_items_in_process("39")
        assert quotas_service.get_max_parallel_work_items_in_process() == 39

    async def test_set_postgres_pool_max_size_too_low(self, storage):
        """Test setting POSTGRES_POOL_MAX_SIZE too low fails."""
        StorageService.set_for_testing(storage)
        QuotasService._instance = None

        quotas_service = await QuotasService.get_instance()

        # First, set PARALLEL_WORK_ITEMS to 20
        await quotas_service.set_max_parallel_work_items_in_process("20")
        assert quotas_service.get_max_parallel_work_items_in_process() == 20

        # Now attempt to set POSTGRES_POOL_MAX_SIZE to 24
        # 80% of 24 = 19.2 (int truncates to 19), which is < 20
        # This should fail
        with pytest.raises(PlatformHTTPError) as exc_info:
            await quotas_service.set_postgres_pool_max_size("24")

        # Verify error details
        from agent_platform.core.errors.responses import ErrorCode

        error = exc_info.value
        assert error.response.error_code is ErrorCode.BAD_REQUEST
        assert "PARALLEL_WORK_ITEMS (20) cannot exceed 80%" in error.detail
        assert "POSTGRES_POOL_MAX_SIZE (24)" in error.detail

    async def test_set_postgres_pool_max_size_to_valid_value(self, storage):
        """Test setting POSTGRES_POOL_MAX_SIZE high enough succeeds."""
        StorageService.set_for_testing(storage)
        QuotasService._instance = None

        quotas_service = await QuotasService.get_instance()

        # First, set PARALLEL_WORK_ITEMS to 20
        await quotas_service.set_max_parallel_work_items_in_process("20")
        assert quotas_service.get_max_parallel_work_items_in_process() == 20

        # Set POSTGRES_POOL_MAX_SIZE to 25
        # 80% of 25 = 20, exactly at threshold - should succeed
        await quotas_service.set_postgres_pool_max_size("25")
        assert quotas_service.get_postgres_pool_max_size() == 25

        # Set POSTGRES_POOL_MAX_SIZE to 100
        # 80% of 100 = 80, well above 20 - should succeed
        await quotas_service.set_postgres_pool_max_size("100")
        assert quotas_service.get_postgres_pool_max_size() == 100
