import typing

import pytest

if typing.TYPE_CHECKING:
    from agent_platform.server.storage.postgres import PostgresStorage


@pytest.fixture(
    params=[
        pytest.param("postgres", marks=[pytest.mark.postgresql]),
    ]
)
async def storage(
    postgres_storage: "PostgresStorage",
):
    """
    Provides the postgres storage instance (named as `storage` so that tests under postgres can use
    it just as `storage` to avoid having to change the name of the fixture)
    """
    return postgres_storage


@pytest.fixture
async def sample_user_id(storage: "PostgresStorage") -> str:
    return await storage.get_system_user_id()
