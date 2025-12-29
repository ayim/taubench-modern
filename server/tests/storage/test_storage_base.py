import typing
from pathlib import Path

import pytest

if typing.TYPE_CHECKING:
    from agent_platform.server.storage.postgres import PostgresStorage
    from agent_platform.server.storage.sqlite import SQLiteStorage


async def _insert_into_agent_config_with_sqlalchemy(storage, conn, config_value: int = 0):
    import json
    import uuid
    from datetime import UTC, datetime

    import sqlalchemy as sa

    from agent_platform.core.configurations.config_validation import ConfigType
    from agent_platform.server.storage.sqlite.sqlite import SQLiteStorage

    agent_config_table = storage._get_table("agent_config")
    stmt = sa.insert(agent_config_table).values(
        {
            "id": str(uuid.uuid4()),
            "config_type": ConfigType.MAX_AGENTS,
            "namespace": "global",
            "config_value": (
                json.dumps({"value": config_value}) if isinstance(storage, SQLiteStorage) else {"value": config_value}
            ),
            "updated_at": datetime.now(UTC),
        }
    )
    await conn.execute(stmt)


async def _set_config_value_with_sqlalchemy(storage, conn, config_value: int):
    import json

    import sqlalchemy as sa

    from agent_platform.core.configurations.config_validation import ConfigType
    from agent_platform.server.storage.sqlite.sqlite import SQLiteStorage

    agent_config_table = storage._get_table("agent_config")
    stmt = (
        sa.update(agent_config_table)
        .where(agent_config_table.c.config_type == ConfigType.MAX_AGENTS and agent_config_table.c.namespace == "global")
        .values(
            config_value=(
                json.dumps({"value": config_value}) if isinstance(storage, SQLiteStorage) else {"value": config_value}
            )
        )
    )
    await conn.execute(stmt)


async def _select_config_values_with_sqlalchemy(storage, conn) -> int | None:
    import json

    import sqlalchemy as sa

    from agent_platform.core.configurations.config_validation import ConfigType
    from agent_platform.server.storage.postgres.postgres import PostgresStorage

    agent_config_table = storage._get_table("agent_config")
    stmt = sa.select(agent_config_table.c.config_value).where(
        agent_config_table.c.config_type == ConfigType.MAX_AGENTS and agent_config_table.c.namespace == "global"
    )
    result = await conn.execute(stmt)
    row = result.fetchone()

    if row is None:
        return None

    return int(row[0]["value"]) if isinstance(storage, PostgresStorage) else int(json.loads(row[0])["value"])


async def _select_config_values_with_raw_cursor(storage: "PostgresStorage|SQLiteStorage", cur) -> int | None:
    import json

    from agent_platform.core.configurations.config_validation import ConfigType
    from agent_platform.server.storage.postgres.postgres import PostgresStorage

    if isinstance(storage, PostgresStorage):
        await cur.execute(
            """SELECT * FROM v2.agent_config WHERE config_type = %(config_type)s
                AND namespace = %(namespace)s""",
            {"config_type": ConfigType.MAX_AGENTS, "namespace": "global"},
        )
    else:
        await cur.execute(
            """SELECT * FROM v2_agent_config WHERE config_type = :config_type
                AND namespace = :namespace""",
            {"config_type": ConfigType.MAX_AGENTS, "namespace": "global"},
        )
    result = await cur.fetchone()
    if result is None:
        return None

    if isinstance(storage, PostgresStorage):
        return int(result["config_value"]["value"])
    else:
        return int(json.loads(result["config_value"])["value"])


async def _insert_into_agent_config(
    storage: "PostgresStorage|SQLiteStorage", cur, config_value: str | int = "10"
) -> str:
    import json
    import uuid
    from datetime import UTC, datetime

    from agent_platform.core.configurations.config_validation import ConfigType
    from agent_platform.server.storage.postgres.postgres import PostgresStorage

    used_uuid = str(uuid.uuid4())

    if isinstance(storage, PostgresStorage):
        await cur.execute(
            """
            INSERT INTO v2.agent_config (id, config_type, namespace, config_value, updated_at)
            VALUES (%(id)s, %(config_type)s, %(namespace)s, %(config_value)s::jsonb, %(updated_at)s)
            """,
            {
                "id": used_uuid,
                "config_type": ConfigType.MAX_AGENTS,
                "namespace": "global",
                "config_value": json.dumps({"value": config_value}),
                "updated_at": datetime.now(UTC).isoformat(),
            },
        )
    else:
        await cur.execute(
            """
            INSERT INTO v2_agent_config (id, config_type, namespace, config_value, updated_at)
            VALUES (:id, :config_type, :namespace, :config_value, :updated_at)
            """,
            {
                "id": used_uuid,
                "config_type": ConfigType.MAX_AGENTS,
                "namespace": "global",
                "config_value": json.dumps({"value": config_value}),
                "updated_at": datetime.now(UTC).isoformat(),
            },
        )
    return used_uuid


@pytest.mark.asyncio
async def test_base_storage_transaction(storage: "PostgresStorage|SQLiteStorage", tmp_path: Path):
    # This test should check that the transaction can be used multiple times by the same coroutine.
    # Nested transactions should auto-rollback on error and the outer transaction may still
    # succeed and commit.

    with pytest.raises(RuntimeError, match="Full auto-rollback on error"):  # noqa: PT012
        # Scenario: multiple roolbacks, nothing committed
        async with storage._write_connection() as conn_initial:
            await _insert_into_agent_config_with_sqlalchemy(storage, conn_initial, 0)
            async with storage._write_connection() as conn_nested:
                await _set_config_value_with_sqlalchemy(storage, conn_nested, 20)

            # Check that the config value is 20
            async with storage._read_connection() as conn_nested_read:
                assert await _select_config_values_with_sqlalchemy(storage, conn_nested_read) == 20

            # Can use transaction again after nested one exits
            await _set_config_value_with_sqlalchemy(storage, conn_initial, 30)

            # Check that the config value is 30
            async with storage._read_connection() as conn_nested_read:
                assert await _select_config_values_with_sqlalchemy(storage, conn_nested_read) == 30

            # Now, set but raise exception in the middle
            with pytest.raises(RuntimeError, match="Should auto-rollback on error"):  # noqa: PT012
                async with storage._write_connection() as conn_nested:
                    await _set_config_value_with_sqlalchemy(storage, conn_nested, 40)
                    raise RuntimeError("Should auto-rollback on error")

            # Check that the config value is still 30 (auto-rollback on error)
            async with storage._read_connection() as conn6:
                assert await _select_config_values_with_sqlalchemy(storage, conn6) == 30

            raise RuntimeError("Full auto-rollback on error")

    # Check: nothing should be in the db!
    async with storage._read_connection() as conn_read_initial:
        assert await _select_config_values_with_sqlalchemy(storage, conn_read_initial) is None

    # --- Scenario: outer committed
    async with storage._write_connection() as conn_initial:
        await _insert_into_agent_config_with_sqlalchemy(storage, conn_initial, 10)

        with pytest.raises(RuntimeError, match="Nested auto-rollback on error"):  # noqa: PT012
            async with storage._write_connection() as conn_nested:
                await _set_config_value_with_sqlalchemy(storage, conn_nested, 20)
                raise RuntimeError("Nested auto-rollback on error")

    async with storage._read_connection() as conn:
        assert await _select_config_values_with_sqlalchemy(storage, conn) == 10

    # --- Scenario: nested committed
    async with storage._write_connection() as conn_initial:
        await _set_config_value_with_sqlalchemy(storage, conn_initial, 22)

        async with storage._write_connection() as conn_nested:
            await _set_config_value_with_sqlalchemy(storage, conn_nested, 33)

    async with storage._read_connection() as conn:
        assert await _select_config_values_with_sqlalchemy(storage, conn) == 33


@pytest.fixture
async def sample_user_id(storage: "SQLiteStorage|PostgresStorage") -> str:
    return await storage.get_system_user_id()


async def test_base_storage_transaction_rollback(
    storage: "SQLiteStorage|PostgresStorage",
    sample_user_id: str,
    sample_agent,
):
    from agent_platform.server.storage.errors import AgentNotFoundError

    with pytest.raises(RuntimeError):  # noqa: PT012
        async with storage._transaction():
            await storage.upsert_agent(sample_user_id, sample_agent)
            raise RuntimeError("Should auto-rollback on error")

    with pytest.raises(AgentNotFoundError):
        await storage.get_agent_by_name(sample_user_id, sample_agent.name)


@pytest.mark.asyncio
async def test_base_storage_cursor_transaction_rollback(storage: "SQLiteStorage|PostgresStorage"):
    try:
        async with storage._transaction() as cur:
            await _insert_into_agent_config(storage, cur)
            raise RuntimeError("Should auto-rollback on error")
    except RuntimeError:
        pass
    else:
        raise AssertionError("Expected RuntimeError")

    async with storage._cursor() as cur:
        assert await _select_config_values_with_raw_cursor(storage, cur) is None

    # Now, commit on success
    async with storage._transaction() as cur:
        await _insert_into_agent_config(storage, cur, 10)

    async with storage._cursor() as cur:
        assert await _select_config_values_with_raw_cursor(storage, cur) == 10

    # Check that mixing and matching _cursor/_transaction and
    # _read_connection/_write_connection works.
    async with storage._write_connection() as conn_initial:
        await _set_config_value_with_sqlalchemy(storage, conn_initial, 55)

        async with storage._cursor() as cur:
            assert await _select_config_values_with_raw_cursor(storage, cur) == 55

        async with storage._read_connection() as conn:
            assert await _select_config_values_with_sqlalchemy(storage, conn) == 55

            with pytest.raises(RuntimeError, match="Nested auto-rollback on error"):  # noqa: PT012
                async with storage._write_connection() as conn_nested:
                    await _set_config_value_with_sqlalchemy(storage, conn_nested, 99)

                    assert await _select_config_values_with_raw_cursor(storage, cur) == 99
                    raise RuntimeError("Nested auto-rollback on error")

                assert await _select_config_values_with_raw_cursor(storage, cur) == 55

    async with storage._read_connection() as conn:
        assert await _select_config_values_with_sqlalchemy(storage, conn) == 55


@pytest.mark.asyncio
async def test_base_storage_transaction_lock(sqlite_storage: "SQLiteStorage"):
    import asyncio
    import json

    from agent_platform.core.configurations.config_validation import ConfigType

    storage = sqlite_storage

    async with storage._transaction() as cur:
        use_id = await _insert_into_agent_config(storage, cur, "0")
        assert use_id is not None

    # Now, create multiple tasks that will increment a value from an existing
    # value (and in the end due to the write lock the final value must be correct).
    async def increment_value():
        async with storage._transaction() as cur:
            # Get the "config_value" and increment it.
            await cur.execute(
                """
                SELECT config_value FROM v2_agent_config WHERE config_type = :config_type
                AND namespace = :namespace
                """,
                {
                    "config_type": ConfigType.MAX_AGENTS,
                    "namespace": "global",
                },
            )
            result = await cur.fetchone()
            assert result is not None
            as_dict = json.loads(result["config_value"])
            result = int(as_dict["value"])

            await _update_agent_config(cur, use_id, str(result + 1))

    times = 1000
    tasks = [increment_value() for _ in range(times)]
    await asyncio.gather(*tasks)

    async with storage._cursor() as cur:
        await cur.execute(
            """
            SELECT config_value FROM v2_agent_config WHERE config_type = :config_type
            AND namespace = :namespace
            """,
            {
                "config_type": ConfigType.MAX_AGENTS,
                "namespace": "global",
            },
        )
        config_value = await cur.fetchone()
        assert config_value is not None
        assert json.loads(config_value["config_value"])["value"] == str(times)


async def _update_agent_config(cur, use_id: str, config_value: str):
    import json

    await cur.execute(
        """
                    UPDATE v2_agent_config
                    SET config_value = :config_value
                    WHERE id = :id
                    """,
        {
            "id": use_id,
            "config_value": json.dumps({"value": config_value}),
        },
    )
