from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest

from sema4ai_agent_server.storage.v2.sqlite_v2 import SQLiteStorageV2


@pytest.fixture(autouse=True)
def _disable_logging() -> Generator[None, None, None]:
    """Disable certain logging for all tests in this directory."""
    from logging import CRITICAL, INFO

    from structlog import get_logger

    # Disable logging for the SQLite storage module (to keep test output clean)
    get_logger("sema4ai_agent_server.storage.v2.sqlite_v2.migrations").setLevel(CRITICAL)
    get_logger("sema4ai_agent_server.storage.v2.sqlite_v2.sqlite").setLevel(CRITICAL)
    yield
    get_logger("sema4ai_agent_server.storage.v2.sqlite_v2.migrations").setLevel(INFO)
    get_logger("sema4ai_agent_server.storage.v2.sqlite_v2.sqlite").setLevel(INFO)


@pytest.fixture
async def storage(tmp_path: Path) -> AsyncGenerator[SQLiteStorageV2, None]:
    """
    Initialize SQLiteStorageV2 with an ephemeral database.
    We'll also seed a system user, just like in Postgres tests.
    """
    test_file_path = tmp_path / "test_sqlite_storage.db"
    storage_instance = SQLiteStorageV2(db_path=str(test_file_path))
    if test_file_path.exists():
        test_file_path.unlink()
    await storage_instance.setup_v2()
    await storage_instance.get_or_create_user_v2(sub="tenant:testing:system:system_user")
    yield storage_instance
    await storage_instance.teardown_v2()
    test_file_path.unlink()


@pytest.fixture
async def sample_user_id(storage: SQLiteStorageV2) -> str:
    return await storage.get_system_user_id_v2()

