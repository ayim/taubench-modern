from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest


@asynccontextmanager
async def sqlite_storage(tmp_path: Path):
    from agent_platform.server.storage.sqlite import SQLiteStorage

    storage = SQLiteStorage(db_path=str(tmp_path / "db_path.db"))
    await storage.setup()
    try:
        yield storage
    finally:
        await storage.teardown()


@pytest.mark.asyncio
async def test_reentry_lock():
    import asyncio
    from asyncio.tasks import wait_for

    from agent_platform.server.storage.sqlite.sqlite import NonReentrantAsyncLock, ReentryError

    lock = NonReentrantAsyncLock()
    async with lock as lock_return:
        assert lock_return is lock, f"{lock_return} is not {lock}"
        assert lock._lock.locked()
        with pytest.raises(ReentryError):
            async with lock as lock:
                pass

    acquired_in_sub = False

    # Now, lock here, create a coroutine that waits for 1 second, and then release the lock
    async def wait_and_release():
        async with lock:
            nonlocal acquired_in_sub
            acquired_in_sub = True

    async with lock:
        t = asyncio.create_task(wait_and_release())
        await asyncio.sleep(0.2)
        assert not acquired_in_sub
    await wait_for(t, timeout=0.2)
    assert acquired_in_sub


@pytest.mark.asyncio
async def test_sqlite_transaction_rollback(tmp_path: Path):
    async with sqlite_storage(tmp_path) as storage:
        try:
            async with storage._transaction() as cur:
                await _insert_into_agent_config(cur)
                raise RuntimeError("Should auto-rollback on error")
        except RuntimeError:
            pass
        else:
            raise AssertionError("Expected RuntimeError")

        async with storage._cursor() as cur:
            await cur.execute("SELECT * FROM v2_agent_config")
            result = await cur.fetchall()
            assert not result

        # Now, commit on success
        async with storage._transaction() as cur:
            await _insert_into_agent_config(cur)

        async with storage._cursor() as cur:
            await cur.execute("SELECT * FROM v2_agent_config")
            result = await cur.fetchall()
            assert result


def create_insert_agent_config_statement(storage) -> Any:
    from datetime import UTC, datetime

    import sqlalchemy as sa

    from agent_platform.core.configurations.config_validation import ConfigType

    return sa.insert(storage._get_table("agent_config")).values(
        {
            "id": "1",
            "config_type": ConfigType.MAX_AGENTS,
            "namespace": "global",
            "config_value": "10",
            "updated_at": datetime.now(UTC),
        }
    )


@pytest.mark.asyncio
async def test_sqlite_transaction_rollback_sqlalchemy(tmp_path: Path):
    async with sqlite_storage(tmp_path) as storage:
        import sqlalchemy as sa

        try:
            async with storage._write_connection() as con:
                stmt = create_insert_agent_config_statement(storage)
                await con.execute(stmt)
                raise RuntimeError("Should auto-rollback on error")
        except RuntimeError:
            pass
        else:
            raise AssertionError("Expected RuntimeError")

        async with storage._read_connection() as con:
            stmt = sa.select(storage._get_table("agent_config"))
            rows = await con.execute(stmt)
            result = rows.fetchall()
            assert not result

        # Now, commit on success
        async with storage._write_connection() as con:
            stmt = create_insert_agent_config_statement(storage)
            await con.execute(stmt)

        async with storage._cursor() as cur:
            await cur.execute("SELECT * FROM v2_agent_config")
            result = await cur.fetchall()
            assert result


@pytest.mark.asyncio
async def test_sqlite_transaction_lock(tmp_path: Path):
    import asyncio

    from agent_platform.core.configurations.config_validation import ConfigType

    async with sqlite_storage(tmp_path) as storage:
        async with storage._transaction() as cur:
            use_id = await _insert_into_agent_config(cur, "0")
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
                result = int(str(result["config_value"]))

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
            assert config_value["config_value"] == str(times)


async def _update_agent_config(cur, use_id: str, config_value: str):
    await cur.execute(
        """
                    UPDATE v2_agent_config
                    SET config_value = :config_value
                    WHERE id = :id
                    """,
        {
            "id": use_id,
            "config_value": config_value,
        },
    )


async def _insert_into_agent_config(cur, config_value: str = "10") -> str:
    import uuid
    from datetime import UTC, datetime

    from agent_platform.core.configurations.config_validation import ConfigType

    used_uuid = str(uuid.uuid4())

    await cur.execute(
        """
        INSERT INTO v2_agent_config (id, config_type, namespace, config_value, updated_at)
        VALUES (:id, :config_type, :namespace, :config_value, :updated_at)
        """,
        {
            "id": used_uuid,
            "config_type": ConfigType.MAX_AGENTS,
            "namespace": "global",
            "config_value": config_value,
            "updated_at": datetime.now(UTC).isoformat(),
        },
    )
    return used_uuid


@pytest.mark.asyncio
async def test_sqlite_base_storage_reentry_failure(tmp_path: Path):
    from agent_platform.server.storage.sqlite.sqlite import ReentryError

    async with sqlite_storage(tmp_path) as storage:
        async with storage._transaction() as cur:
            await _insert_into_agent_config(cur)
            with pytest.raises(ReentryError):
                async with storage._transaction():  # Reentry should be a failure
                    pass


@pytest.mark.asyncio
async def test_sqlite_base_storage_check_user_access(tmp_path: Path):
    from sema4ai.common.null import NULL

    async with sqlite_storage(tmp_path) as storage:
        # Now, test that calling the `check_user_access` function works.
        async with storage._cursor() as cur:
            await cur.execute(
                "SELECT v2_check_user_access(?, ?) AS check_user_access",
                ("foo", "bar"),
            )
            result = await cur.fetchone()
            assert result is not None
            assert result["check_user_access"] == 0

        async with storage._transaction() as cur:
            logger = storage._logger
            storage._logger = NULL  # Disable logging

            try:
                # Let's drop table 'v2_user' to make an exception happen in the select.
                await cur.execute("DROP TABLE IF EXISTS v2_user")
                await cur.execute(
                    "SELECT v2_check_user_access(?, ?) AS check_user_access",
                    ("foo", "bar"),
                )
            finally:
                storage._logger = logger
            result = await cur.fetchone()
            assert result is not None
            assert result["check_user_access"] == 0

        # Would like to see some more test coverage in the `check_user_access` function,
        # but leaving that for another day...
