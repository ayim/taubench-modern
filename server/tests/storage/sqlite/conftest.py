import typing

import pytest

if typing.TYPE_CHECKING:
    from agent_platform.server.storage.sqlite import SQLiteStorage


@pytest.fixture
def storage(sqlite_storage: "SQLiteStorage") -> "SQLiteStorage":
    """
    Provides the sqlite storage instance (named as `storage` so that tests under sqlite can use
    it just as `storage` to avoid having to change the name of the fixture)
    """
    return sqlite_storage


@pytest.fixture
async def sample_user_id(storage: "SQLiteStorage") -> str:
    return await storage.get_system_user_id()
