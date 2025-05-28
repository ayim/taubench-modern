from abc import ABC, abstractmethod
from typing import Any

import structlog
from aiosqlite import connect
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

logger = structlog.get_logger(__name__)


class StorageInterface(ABC):
    """Abstract base class for database storage interfaces"""

    @abstractmethod
    async def connect(self) -> None:
        """Establish connection to the database"""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the database connection"""
        pass

    @abstractmethod
    async def get_all_agents(self) -> list[dict[str, Any]]:
        """Retrieve all agents from the database"""
        pass

    @abstractmethod
    async def insert_agent(self, agent_data: dict[str, Any]) -> None:
        """Insert agent data into the database"""
        pass

    @abstractmethod
    async def get_all_threads(self) -> list[dict[str, Any]]:
        """Retrieve all threads from the database"""
        pass

    @abstractmethod
    async def insert_thread(self, thread_data: dict[str, Any]) -> None:
        """Insert thread data into the database"""
        pass

    @abstractmethod
    async def get_latest_checkpoint(self, thread_id: str) -> dict[str, Any]:
        """Retrieve the latest checkpoint for a thread"""
        pass

    @abstractmethod
    async def insert_v2_thread_message(self, thread_message_data: dict[str, Any]) -> None:
        """Insert v2 thread message data into the database"""
        pass

    @abstractmethod
    async def count_v1_agents(self) -> int:
        """Count the number of v1 agents in the database"""
        pass

    @abstractmethod
    async def count_v2_agents(self) -> int:
        """Count the number of v2 agents in the database"""
        pass

    @abstractmethod
    async def get_all_users(self) -> list[dict[str, Any]]:
        """Retrieve all users from the database"""
        pass

    @abstractmethod
    async def insert_user(self, user_data: dict[str, Any]) -> None:
        """Insert user data into the database"""
        pass


class SQLiteStorage(StorageInterface):
    """SQLite implementation of the storage interface"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.write_db_path = "agentserver.db"
        self.connection = None

    async def connect(self) -> None:
        """Connect to the SQLite database"""
        self.connection = await connect(self.db_path)
        self.write_connection = await connect(self.write_db_path)

    async def close(self) -> None:
        """Close the SQLite connection"""
        if self.connection:
            await self.connection.close()
            self.connection = None
        if self.write_connection:
            await self.write_connection.close()
            self.write_connection = None

    async def get_all_agents(self) -> list[dict[str, Any]]:
        """Get all agents from the SQLite database"""
        if not self.connection:
            raise RuntimeError("Not connected to database")

        cursor = await self.connection.execute("SELECT * FROM agent")
        rows = await cursor.fetchall()
        column_names = [description[0] for description in cursor.description]

        return [dict(zip(column_names, row, strict=False)) for row in rows]

    async def insert_agent(self, agent_data: dict[str, Any]) -> None:
        """Insert agent into the SQLite database"""
        if not self.write_connection:
            raise RuntimeError("Not connected to database")

        try:
            await self.write_connection.execute(
                """
                INSERT INTO v2_agent (
                    agent_id, name, description, user_id, runbook_structured,
                    version, created_at, updated_at, action_packages,
                    mcp_servers, agent_architecture, question_groups,
                    observability_configs, platform_configs, extra, mode
                )
                VALUES (
                    :agent_id, :name, :description, :user_id, :runbook_structured,
                    :version, :created_at, :updated_at, :action_packages,
                    :mcp_servers, :agent_architecture, :question_groups,
                    :observability_configs, :platform_configs, :extra, :mode
                )
                ON CONFLICT DO NOTHING
                """,
                agent_data,
            )
            await self.write_connection.commit()
        except Exception as e:
            logger.error(f"Error inserting agent: {e}")
            raise

    async def get_all_threads(self) -> list[dict[str, Any]]:
        """Get all threads from the SQLite database"""
        if not self.connection:
            raise RuntimeError("Not connected to database")

        cursor = await self.connection.execute("SELECT * FROM thread")
        rows = await cursor.fetchall()
        column_names = [description[0] for description in cursor.description]

        return [dict(zip(column_names, row, strict=False)) for row in rows]

    async def insert_thread(self, thread_data: dict[str, Any]) -> None:
        """Insert thread into the SQLite database"""
        if not self.write_connection:
            raise RuntimeError("Not connected to database")

        try:
            await self.write_connection.execute(
                """
                INSERT INTO v2_thread (
                    thread_id, agent_id, user_id, name, created_at, updated_at, metadata
                )
                VALUES (
                    :thread_id, :agent_id, :user_id, :name, :created_at, :updated_at, :metadata
                )
                ON CONFLICT DO NOTHING
                """,
                thread_data,
            )
            await self.write_connection.commit()
        except Exception as e:
            logger.error(f"Error inserting thread {thread_data.get('name', 'unknown')}: {e}")
            raise

    async def get_latest_checkpoint(self, thread_id: str) -> dict[str, Any]:
        """Get the latest checkpoint for a thread from the SQLite database"""
        if not self.connection:
            raise RuntimeError("Not connected to database")

        cursor = await self.connection.execute(
            """
            SELECT thread_id, checkpoint_ns,
                checkpoint_id, parent_checkpoint_id,
                checkpoint, metadata
            FROM checkpoints
            WHERE thread_id = ?
            """,
            (thread_id,),
        )
        rows = await cursor.fetchall()

        if rows:
            column_names = [description[0] for description in cursor.description]
            checkpoints = [dict(zip(column_names, row, strict=False)) for row in rows]
        else:
            checkpoints = []

        is_parent_checkpoint = {}
        for checkpoint in checkpoints:
            is_parent_checkpoint[checkpoint["parent_checkpoint_id"]] = True

        for checkpoint in checkpoints:
            if checkpoint["checkpoint_id"] not in is_parent_checkpoint:
                return checkpoint

        return {}

    async def insert_v2_thread_message(self, thread_message_data: dict[str, Any]) -> None:
        """Insert v2 thread message data into the SQLite database"""
        if not self.write_connection:
            raise RuntimeError("Not connected to database")

        try:
            await self.write_connection.execute(
                """
                INSERT INTO v2_thread_message (
                    message_id, sequence_number, thread_id, parent_run_id,
                    created_at, updated_at, role, content, agent_metadata, server_metadata
                )
                VALUES (
                    :message_id, :sequence_number, :thread_id, :parent_run_id,
                    :created_at, :updated_at, :role, :content, :agent_metadata, :server_metadata
                )
                ON CONFLICT DO NOTHING
                """,
                thread_message_data,
            )
            await self.write_connection.commit()
        except Exception as e:
            logger.error(f"Error inserting thread message: {e}")
            raise

    async def count_v1_agents(self) -> int:
        """Count the number of v1 agents in the database"""
        if not self.connection:
            raise RuntimeError("Not connected to database")

        try:
            cursor = await self.connection.execute("SELECT COUNT(*) FROM agent")
            row = await cursor.fetchone()
            return row[0] if row else 0
        except Exception as e:
            logger.error(f"Error counting v1 agents: {e}")
            return 0

    async def count_v2_agents(self) -> int:
        """Count the number of v2 agents in the database"""
        if not self.write_connection:
            raise RuntimeError("Not connected to database")

        try:
            cursor = await self.write_connection.execute("SELECT COUNT(*) FROM v2_agent")
            row = await cursor.fetchone()
            return row[0] if row else 0
        except Exception as e:
            logger.error(f"Error counting v2 agents: {e}")
            return 0

    async def get_all_users(self) -> list[dict[str, Any]]:
        """Get all users from the SQLite database"""
        if not self.connection:
            raise RuntimeError("Not connected to database")

        cursor = await self.connection.execute("SELECT * FROM public.user")
        rows = await cursor.fetchall()
        column_names = [description[0] for description in cursor.description]

        return [dict(zip(column_names, row, strict=False)) for row in rows]

    async def insert_user(self, user_data: dict[str, Any]) -> None:
        """Insert user into the SQLite database"""
        if not self.write_connection:
            raise RuntimeError("Not connected to database")

        try:
            await self.write_connection.execute(
                """
                INSERT INTO v2_user (
                    user_id, sub, created_at
                )
                VALUES (
                    :user_id, :sub, :created_at
                )
                ON CONFLICT DO NOTHING
                """,
                user_data,
            )
            await self.write_connection.commit()
        except Exception as e:
            logger.error(f"Error inserting user: {e}")
            raise


class MigrationPostgresStorage(StorageInterface):
    """PostgreSQL implementation of the storage interface for migration"""

    def __init__(self, connection_url: str):
        self.connection_url = connection_url
        self.storage = None
        self._pool = None
        self.conn = None

    async def connect(self) -> None:
        """Connect to the PostgreSQL database"""
        self._pool = AsyncConnectionPool(
            conninfo=self.connection_url,
            max_size=20,
            num_workers=3,
            open=False,
        )
        await self._pool.open()
        self.conn = await self._pool.getconn()

    async def close(self) -> None:
        """Close the PostgreSQL connection"""
        if self._pool:
            await self._pool.close()
            self._pool = None
            self.conn = None

    async def get_all_agents(self) -> list[dict[str, Any]]:
        """Get all agents from the PostgreSQL database"""
        if not self._pool or not self.conn:
            raise RuntimeError("Not connected to database")

        async with self.conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute("SELECT * FROM agent")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def insert_agent(self, agent_data: dict[str, Any]) -> None:
        """Insert agent into the PostgreSQL database"""
        if not self._pool or not self.conn:
            raise RuntimeError("Not connected to database")

        try:
            async with self.conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    INSERT INTO v2.agent (
                        agent_id, name, description, user_id, runbook_structured,
                        version, created_at, updated_at, action_packages,
                        mcp_servers, agent_architecture, question_groups,
                        observability_configs, platform_configs, extra, mode
                    )
                    VALUES (
                        %(agent_id)s, %(name)s, %(description)s, %(user_id)s,
                        %(runbook_structured)s,
                        %(version)s, %(created_at)s, %(updated_at)s,
                        %(action_packages)s,
                        %(mcp_servers)s, %(agent_architecture)s, %(question_groups)s,
                        %(observability_configs)s, %(platform_configs)s,
                        %(extra)s, %(mode)s
                    )
                    ON CONFLICT DO NOTHING
                    """,
                    agent_data,
                )
            await self.conn.commit()
        except Exception as e:
            logger.error(f"Error inserting agent: {e}")
            raise

    async def get_all_threads(self) -> list[dict[str, Any]]:
        """Get all threads from the PostgreSQL database"""
        if not self._pool or not self.conn:
            raise RuntimeError("Not connected to database")

        async with self.conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute("SELECT * FROM thread")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def insert_thread(self, thread_data: dict[str, Any]) -> None:
        """Insert thread into the PostgreSQL database"""
        if not self._pool or not self.conn:
            raise RuntimeError("Not connected to database")

        try:
            async with self.conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    INSERT INTO v2.thread (
                        thread_id, agent_id, user_id, name, created_at, updated_at, metadata
                    )
                    VALUES (
                        %(thread_id)s, %(agent_id)s, %(user_id)s, %(name)s,
                        %(created_at)s, %(updated_at)s, %(metadata)s
                    )
                    ON CONFLICT DO NOTHING
                    """,
                    thread_data,
                )
            await self.conn.commit()
        except Exception as e:
            logger.error(f"Error inserting thread {thread_data.get('name', 'unknown')}: {e}")
            raise

    async def get_latest_checkpoint(self, thread_id: str) -> dict[str, Any]:
        """Get the latest checkpoint for a thread from the PostgreSQL database"""
        if not self._pool or not self.conn:
            raise RuntimeError("Not connected to database")

        async with self.conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute(
                """
                SELECT thread_id, checkpoint_ns,
                    checkpoint_id, parent_checkpoint_id,
                    checkpoint, metadata
                FROM checkpoints
                WHERE thread_id = %s::text
                """,
                (thread_id,),
            )
            rows = await cursor.fetchall()

            if rows:
                checkpoints = [dict(row) for row in rows]
            else:
                checkpoints = []

            is_parent_checkpoint = {}
            for checkpoint in checkpoints:
                is_parent_checkpoint[checkpoint["parent_checkpoint_id"]] = True

            for checkpoint in checkpoints:
                if checkpoint["checkpoint_id"] not in is_parent_checkpoint:
                    return checkpoint

            return {}

    async def insert_v2_thread_message(self, thread_message_data: dict[str, Any]) -> None:
        """Insert v2 thread message data into the PostgreSQL database"""
        if not self._pool or not self.conn:
            raise RuntimeError("Not connected to database")

        try:
            async with self.conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    INSERT INTO v2.thread_message (
                        message_id, sequence_number, thread_id, parent_run_id,
                        created_at, updated_at, role, content, agent_metadata, server_metadata
                    )
                    VALUES (
                        %(message_id)s, %(sequence_number)s, %(thread_id)s,
                        %(parent_run_id)s, %(created_at)s, %(updated_at)s,
                        %(role)s, %(content)s, %(agent_metadata)s,
                        %(server_metadata)s
                    )
                    ON CONFLICT DO NOTHING
                    """,
                    thread_message_data,
                )
            await self.conn.commit()
        except Exception as e:
            logger.error(f"Error inserting thread message: {e}")
            raise

    async def count_v1_agents(self) -> int:
        """Count the number of v1 agents in the database"""
        if not self._pool or not self.conn:
            raise RuntimeError("Not connected to database")

        try:
            async with self.conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute("SELECT COUNT(*) FROM agent")
                row = await cursor.fetchone()
                count = row["count"] if row else 0
                return count
        except Exception as e:
            import traceback

            logger.error(
                f"Error counting v1 agents: {type(e).__name__}: {e!s}\n{traceback.format_exc()}"
            )
            return 0

    async def count_v2_agents(self) -> int:
        """Count the number of v2 agents in the database"""
        if not self._pool or not self.conn:
            raise RuntimeError("Not connected to database")

        try:
            async with self.conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute("SELECT COUNT(*) FROM v2.agent")
                row = await cursor.fetchone()
                count = row["count"] if row else 0
                return count
        except Exception as e:
            import traceback

            logger.error(
                f"Error counting v2 agents: {type(e).__name__}: {e!s}\n{traceback.format_exc()}"
            )
            return 0

    async def get_all_users(self) -> list[dict[str, Any]]:
        """Get all users from the PostgreSQL database"""
        if not self._pool or not self.conn:
            raise RuntimeError("Not connected to database")

        async with self.conn.cursor(row_factory=dict_row) as cursor:
            await cursor.execute("SELECT * FROM public.user")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def insert_user(self, user_data: dict[str, Any]) -> None:
        """Insert user into the PostgreSQL database"""
        if not self._pool or not self.conn:
            raise RuntimeError("Not connected to database")

        try:
            async with self.conn.cursor(row_factory=dict_row) as cursor:
                await cursor.execute(
                    """
                    INSERT INTO v2.user (
                        user_id, sub, created_at
                    )
                    VALUES (
                        %(user_id)s, %(sub)s, %(created_at)s
                    )
                    ON CONFLICT DO NOTHING
                    """,
                    user_data,
                )
            await self.conn.commit()
        except Exception as e:
            logger.error(f"Error inserting user: {e}")
            raise


def get_storage(db_type: str, db_path: str = "", db_url: str = "") -> StorageInterface:
    """Factory function to get the appropriate storage interface

    Args:
        db_type: Type of database ('sqlite' or 'postgres')
        db_path: Path to SQLite database file
        db_url: PostgreSQL connection URL

    Returns:
        Appropriate storage interface
    """
    if db_type == "sqlite":
        if not db_path:
            raise ValueError("db_path is required for SQLite connection")
        return SQLiteStorage(db_path)
    elif db_type == "postgres":
        if not db_url:
            raise ValueError("db_url is required for PostgreSQL connection")
        return MigrationPostgresStorage(db_url)
    else:
        raise ValueError(f"Unsupported database type: {db_type}")
