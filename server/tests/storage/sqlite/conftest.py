from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest

from agent_platform.server.storage.sqlite import SQLiteStorage


@pytest.fixture(autouse=True)
def _disable_logging() -> Generator[None, None, None]:
    """Disable certain logging for all tests in this directory."""
    from logging import CRITICAL, INFO, getLogger

    # Use Python's standard logging to disable logging for specific modules
    getLogger("agent_platform.storage.sqlite.migrations").setLevel(CRITICAL)
    getLogger("agent_platform.storage.sqlite.sqlite").setLevel(CRITICAL)
    yield
    getLogger("agent_platform.storage.sqlite.migrations").setLevel(INFO)
    getLogger("agent_platform.storage.sqlite.sqlite").setLevel(INFO)


@pytest.fixture
async def storage(tmp_path: Path) -> AsyncGenerator[SQLiteStorage, None]:
    """
    Initialize SQLiteStorage with an ephemeral database.
    We'll also seed a system user, just like in Postgres tests.
    """
    test_file_path = tmp_path / "test_sqlite_storage.db"
    storage_instance = SQLiteStorage(db_path=str(test_file_path))
    if test_file_path.exists():
        test_file_path.unlink()
    await storage_instance.setup()
    await storage_instance.get_or_create_user(
        sub="tenant:testing:system:system_user",
    )
    yield storage_instance
    await storage_instance.teardown()
    test_file_path.unlink()


@pytest.fixture
async def sample_user_id(storage: SQLiteStorage) -> str:
    return await storage.get_system_user_id()
