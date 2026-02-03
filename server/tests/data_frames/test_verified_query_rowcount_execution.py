"""
Integration tests for verified query ROWCOUNT execution.

Tests the real invoke_sql_for_rows_affected() function which is used
for INSERT/UPDATE/DELETE queries without RETURNING clause.
"""

import sqlite3
import typing
from pathlib import Path

import pytest

from server.tests.storage_fixtures import *  # noqa: F403

if typing.TYPE_CHECKING:
    from agent_platform.server.data_frames.data_frames_kernel import DataFramesKernel
    from agent_platform.server.storage.sqlite import SQLiteStorage


class _MutableDataFramesChecker:
    """Helper to set up mutable SQLite tables for testing mutations."""

    def __init__(self, sqlite_storage: "SQLiteStorage", tmpdir: Path):
        from server.tests.storage.sample_model_creator import SampleModelCreator

        self.sqlite_storage = sqlite_storage
        self.tmpdir = tmpdir
        self.model_creator = SampleModelCreator(sqlite_storage, tmpdir)
        self.db_path: Path | None = None
        self.semantic_data_model_name: str | None = None

    async def setup(self):
        from agent_platform.core.user import User

        await self.model_creator.setup()

        user_id = await self.model_creator.get_user_id()
        self.user = User(user_id=user_id, sub="")
        self.agent = await self.model_creator.obtain_sample_agent()
        self.thread = await self.model_creator.obtain_sample_thread()
        self.tid = self.thread.thread_id

    async def create_mutable_sqlite_db(self) -> Path:
        """Create a SQLite database with a users table for mutation testing."""
        from uuid import uuid4

        self.db_path = self.tmpdir / f"mutable_test_{uuid4().hex[:8]}.sqlite"

        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                name TEXT,
                email TEXT
            )
        """)
        conn.execute("INSERT INTO users VALUES (1, 'Alice', 'alice@example.com')")
        conn.execute("INSERT INTO users VALUES (2, 'Bob', 'bob@example.com')")
        conn.execute("INSERT INTO users VALUES (3, 'Charlie', 'charlie@example.com')")
        conn.commit()
        conn.close()

        return self.db_path

    async def setup_semantic_data_model(self) -> str:
        """Create data connection and semantic data model for the mutable DB."""
        from agent_platform.core.semantic_data_model.types import (
            SemanticDataModel,
        )

        # Create data connection
        data_connection = await self.model_creator.obtain_sample_data_connection(
            name="mutable_test_connection",
            db_file_path=self.db_path,
        )

        # Create semantic data model
        semantic_model = {
            "name": "mutable_test_model",
            "description": "Test model for mutation queries",
            "tables": [
                {
                    "name": "users",
                    "base_table": {
                        "data_connection_id": data_connection.id,
                        "table": "users",
                    },
                    "description": "Users table",
                    "dimensions": [
                        {"name": "id", "expr": "id", "data_type": "INTEGER"},
                        {"name": "name", "expr": "name", "data_type": "TEXT"},
                        {"name": "email", "expr": "email", "data_type": "TEXT"},
                    ],
                }
            ],
        }

        sdm = SemanticDataModel(**semantic_model)
        sdm_id = await self.sqlite_storage.set_semantic_data_model(
            semantic_data_model_id=None,
            semantic_model=sdm,
            data_connection_ids=[data_connection.id],
            file_references=[],
        )

        # Assign to agent
        await self.sqlite_storage.set_agent_semantic_data_models(
            agent_id=self.agent.agent_id,
            semantic_data_model_ids=[sdm_id],
        )

        self.semantic_data_model_name = "mutable_test_model"
        return self.semantic_data_model_name

    def create_data_frames_kernel(self) -> "DataFramesKernel":
        from agent_platform.server.data_frames.data_frames_kernel import (
            DataFramesKernel,
        )

        return DataFramesKernel(self.sqlite_storage, self.user, self.tid)

    def get_row_count(self) -> int:
        """Get current row count from the SQLite database."""
        conn = sqlite3.connect(str(self.db_path))
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        conn.close()
        return count


@pytest.fixture
async def mutable_checker(sqlite_storage, tmpdir) -> _MutableDataFramesChecker:
    """Create a checker with mutable SQLite table."""
    checker = _MutableDataFramesChecker(sqlite_storage, Path(tmpdir))
    await checker.setup()
    await checker.create_mutable_sqlite_db()
    await checker.setup_semantic_data_model()
    return checker


@pytest.mark.asyncio
async def test_invoke_sql_for_rows_affected_delete(mutable_checker: _MutableDataFramesChecker):
    """Test DELETE without RETURNING returns correct row count."""
    from agent_platform.server.data_frames.data_frames_from_computation import (
        invoke_sql_for_rows_affected,
    )

    # Verify initial state
    assert mutable_checker.get_row_count() == 3

    rows_affected = await invoke_sql_for_rows_affected(
        data_frames_kernel=mutable_checker.create_data_frames_kernel(),
        sql_query="DELETE FROM users WHERE id = 2",
        dialect="sqlite",
        semantic_data_model_name=mutable_checker.semantic_data_model_name,
    )

    assert rows_affected == 1
    assert mutable_checker.get_row_count() == 2


@pytest.mark.asyncio
async def test_invoke_sql_for_rows_affected_insert(mutable_checker: _MutableDataFramesChecker):
    """Test INSERT without RETURNING returns correct row count."""
    from agent_platform.server.data_frames.data_frames_from_computation import (
        invoke_sql_for_rows_affected,
    )

    assert mutable_checker.get_row_count() == 3

    rows_affected = await invoke_sql_for_rows_affected(
        data_frames_kernel=mutable_checker.create_data_frames_kernel(),
        sql_query="INSERT INTO users (id, name, email) VALUES (4, 'Dave', 'dave@example.com')",
        dialect="sqlite",
        semantic_data_model_name=mutable_checker.semantic_data_model_name,
    )

    assert rows_affected == 1
    assert mutable_checker.get_row_count() == 4


@pytest.mark.asyncio
async def test_invoke_sql_for_rows_affected_update(mutable_checker: _MutableDataFramesChecker):
    """Test UPDATE without RETURNING returns correct row count."""
    from agent_platform.server.data_frames.data_frames_from_computation import (
        invoke_sql_for_rows_affected,
    )

    rows_affected = await invoke_sql_for_rows_affected(
        data_frames_kernel=mutable_checker.create_data_frames_kernel(),
        sql_query="UPDATE users SET email = 'updated@example.com' WHERE id <= 2",
        dialect="sqlite",
        semantic_data_model_name=mutable_checker.semantic_data_model_name,
    )

    assert rows_affected == 2


@pytest.mark.asyncio
async def test_invoke_sql_for_rows_affected_no_match(mutable_checker: _MutableDataFramesChecker):
    """Test DELETE with no matching rows returns 0."""
    from agent_platform.server.data_frames.data_frames_from_computation import (
        invoke_sql_for_rows_affected,
    )

    rows_affected = await invoke_sql_for_rows_affected(
        data_frames_kernel=mutable_checker.create_data_frames_kernel(),
        sql_query="DELETE FROM users WHERE id = 999",
        dialect="sqlite",
        semantic_data_model_name=mutable_checker.semantic_data_model_name,
    )

    assert rows_affected == 0
    assert mutable_checker.get_row_count() == 3  # No change
