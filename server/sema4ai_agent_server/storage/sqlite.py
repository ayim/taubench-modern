import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union
from uuid import uuid4

import structlog
from agent_architecture import FINISH_NODE_KEY
from agent_server_types import (
    AGENT_LIST_ADAPTER,
    MODEL,
    RAW_CONTEXT,
    THREAD_LIST_ADAPTER,
    UPLOADED_FILE_LIST_ADAPTER,
    ActionPackage,
    Agent,
    AgentAdvancedConfig,
    AgentMetadata,
    EmbeddingStatus,
    Thread,
    UploadedFile,
    User,
)
from langchain_core.messages import AnyMessage

from sema4ai_agent_server.agent import runnable_agent
from sema4ai_agent_server.constants import SystemPaths
from sema4ai_agent_server.storage import (
    BaseStorage,
    UniqueAgentNameError,
    UniqueFileRefError,
)
from sema4ai_agent_server.storage.utils import model_dump_for_sqlite

logger = structlog.get_logger()


class SqliteStorage(BaseStorage):
    _is_setup: bool = False

    async def setup(self) -> None:
        if self._is_setup:
            return
        await self._run_migrations()
        self._is_setup = True

    async def teardown(self) -> None:
        pass

    @classmethod
    @contextmanager
    def _connect(cls):
        conn = sqlite3.connect(SystemPaths.domain_database_path)
        conn.row_factory = sqlite3.Row  # Enable dictionary access to row items.
        try:
            yield conn
        finally:
            conn.close()

    async def _run_migrations(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        migrations_path = Path(current_dir).parent / "migrations" / "sqlite"

        with self._connect() as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT name FROM sqlite_master WHERE type='table' AND name='migrations';
            """
            )
            migrations_table_exists = cursor.fetchone() is not None
            if not migrations_table_exists:
                cursor.execute(
                    """
                    CREATE TABLE migrations (
                        version INTEGER PRIMARY KEY, dirty BOOLEAN NOT NULL
                    );
                """
                )
                cursor.execute("INSERT INTO migrations (version, dirty) VALUES (0, 0);")
                conn.commit()

            cursor.execute("SELECT version FROM migrations WHERE dirty = 1")
            dirty_version = cursor.fetchone()
            if dirty_version:
                raise Exception(
                    f"Migration {dirty_version[0]} is dirty. Please fix it manually. "
                    "No migrations will be applied. Please fix it manually."
                )

            # get current version
            cursor.execute("SELECT version FROM migrations;")
            current_version = cursor.fetchone()[0]

            # List and sort migration files
            migration_files = sorted(
                (f for f in os.listdir(migrations_path) if f.endswith(".up.sql")),
                key=lambda x: int(x.split("_")[0]),
            )

            logger.info(f"Migrations found: {migration_files}")
            logger.info(f"Current migration version: {current_version}")

            for migration in migration_files:
                version = int(migration.split("_")[0])
                if version > current_version:
                    logger.info(f"Applying migration {migration}")

                    # Set dirty flag
                    cursor.execute(
                        "UPDATE migrations SET version = ?, dirty = 1", (version,)
                    )
                    conn.commit()
                    # Try to apply the migration
                    with open(os.path.join(migrations_path, migration), "r") as f:
                        cursor.executescript(f.read())
                        conn.commit()
                    # Unset dirty flag
                    cursor.execute("UPDATE migrations SET dirty = 0")
                    conn.commit()

                    current_version = version

    async def list_agents(self, user_id: str) -> List[Agent]:
        """List all agents for the current user."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM agent WHERE user_id = ? OR public = 1", (user_id,)
            )
            rows = cursor.fetchall()

            return AGENT_LIST_ADAPTER.validate_python([dict(row) for row in rows])

    async def list_all_agents(self) -> List[Agent]:
        """List all agents for all users."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM agent")
            rows = cursor.fetchall()

            return AGENT_LIST_ADAPTER.validate_python([dict(row) for row in rows])

    async def get_agent(self, user_id: str, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM agent WHERE id = ? AND (user_id = ? OR public = 1)",
                (agent_id, user_id),
            )
            row = cursor.fetchone()
            return Agent.model_validate(dict(row)) if row else None

    async def put_agent(
        self,
        user_id: str,
        agent_id: str,
        *,
        public: bool,
        name: str,
        description: str,
        runbook: str,
        version: str,
        model: MODEL,
        advanced_config: AgentAdvancedConfig,
        action_packages: list[ActionPackage],
        metadata: AgentMetadata,
        created_at: datetime,
    ) -> Agent:
        """Modify an agent."""
        updated_at = datetime.now(timezone.utc)
        # validate first
        new_agent = Agent(
            id=agent_id,
            user_id=user_id,
            public=public,
            name=name,
            description=description,
            runbook=runbook,
            version=version,
            model=model,
            advanced_config=advanced_config,
            action_packages=action_packages,
            updated_at=updated_at,
            created_at=created_at,
            metadata=metadata,
        )
        with self._connect() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO agent (id, user_id, public, name, description, runbook, version, model, advanced_config, action_packages, updated_at, metadata, created_at)
                    VALUES (:id, :user_id, :public, :name, :description, :runbook, :version, :model, :advanced_config, :action_packages, :updated_at, :metadata, :created_at)
                    ON CONFLICT(id) 
                    DO UPDATE SET 
                        user_id = EXCLUDED.user_id, 
                        public = EXCLUDED.public,
                        name = EXCLUDED.name, 
                        description = EXCLUDED.description,
                        runbook = EXCLUDED.runbook,
                        version = EXCLUDED.version,
                        model = EXCLUDED.model,
                        advanced_config = EXCLUDED.advanced_config,
                        action_packages = EXCLUDED.action_packages,
                        updated_at = EXCLUDED.updated_at, 
                        metadata = EXCLUDED.metadata,
                        created_at=EXCLUDED.created_at
                    """,
                    model_dump_for_sqlite(new_agent, RAW_CONTEXT),
                )
                conn.commit()
            except sqlite3.IntegrityError as e:
                conn.commit()
                if (
                    e.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_UNIQUE
                    and "agent.name" in str(e)
                ):
                    raise UniqueAgentNameError(name)
                raise e
            return new_agent

    async def agent_count(self) -> int:
        """Get agent row count"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM agent")
            count = cursor.fetchone()[0]
            return count

    async def list_threads(
        self, user_id: str, aid: str = None, name: str = None, limit: int = None
    ) -> List[Thread]:
        """List all threads for the current user and system threads."""
        sql = """
                SELECT t.* 
                FROM thread t
                LEFT JOIN "user" u ON t.user_id = u.user_id
                WHERE (t.user_id = ? OR u.sub LIKE 'tenant:%:system:system_user')
                """
        params = [user_id]

        if aid is not None:
            sql += " AND t.agent_id = ?"
            params.append(aid)

        if name is not None:
            sql += " AND t.name LIKE ?"
            params.append(f"%{name}%")

        sql += " ORDER BY t.updated_at DESC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(limit)

        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()

            return THREAD_LIST_ADAPTER.validate_python([dict(row) for row in rows])

    async def get_thread(self, user_id: str, thread_id: str) -> Optional[Thread]:
        """Get a thread by ID, including system threads."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT t.* 
                FROM thread t
                LEFT JOIN "user" u ON t.user_id = u.user_id
                WHERE t.thread_id = ? 
                AND (t.user_id = ? OR u.sub LIKE 'tenant:%:system:system_user')
                """,
                (thread_id, user_id),
            )
            row = cursor.fetchone()
            return Thread.model_validate(dict(row)) if row else None

    async def thread_count(self) -> int:
        """Get thread row count."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM thread")
            count = cursor.fetchone()[0]
            return count

    async def get_thread_state(self, thread_id: str):
        """Get state for a thread."""
        # TODO: importing runnable_agent might be too heavy for this method
        state = runnable_agent.get_state({"configurable": {"thread_id": thread_id}})
        return {
            "values": state.values,
            "next": state.next,
        }

    async def update_thread_state(
        self,
        thread_id: str,
        values: Union[Sequence[AnyMessage], Dict[str, Any]],
        as_node: Optional[str] = FINISH_NODE_KEY,
    ):
        """Add state to a thread."""
        # TODO: importing runnable_agent might be too heavy for this method
        retval = runnable_agent.update_state(
            {"configurable": {"thread_id": thread_id}}, values, as_node=as_node
        )
        return retval

    async def get_thread_history(self, thread_id: str):
        """Get the history of a thread."""
        # TODO: importing runnable_agent might be too heavy for this method
        return [
            {
                "values": c.values,
                "next": c.next,
                "config": c.config,
                "parent": c.parent_config,
            }
            for c in runnable_agent.get_state_history(
                {"configurable": {"thread_id": thread_id}}
            )
        ]

    async def put_thread(
        self,
        user_id: str,
        thread_id: str,
        *,
        agent_id: str,
        name: str,
        metadata: Optional[dict],
        created_at: datetime,
    ) -> Thread:
        """Modify a thread."""
        updated_at = datetime.now(timezone.utc)
        # validate first
        new_thread = Thread(
            thread_id=thread_id,
            user_id=user_id,
            agent_id=agent_id,
            name=name,
            updated_at=updated_at,
            metadata=metadata,
            created_at=created_at,
        )
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO thread (thread_id, user_id, agent_id, name, updated_at, metadata, created_at)
                VALUES (:thread_id, :user_id, :agent_id, :name, :updated_at, :metadata, :created_at)
                ON CONFLICT(thread_id) 
                DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    agent_id = EXCLUDED.agent_id, 
                    name = EXCLUDED.name, 
                    updated_at = EXCLUDED.updated_at,
                    metadata = EXCLUDED.metadata,
                    created_at = EXCLUDED.created_at
                """,
                model_dump_for_sqlite(new_thread, RAW_CONTEXT),
            )
            conn.commit()
            return new_thread

    async def get_or_create_user(self, sub: str) -> tuple[User, bool]:
        """Returns a tuple of the user and a boolean indicating whether the user was created."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM "user" WHERE sub = ?', (sub,))
            user_row = cursor.fetchone()

            if user_row:
                return User.model_validate(dict(user_row)), False

            # SQLite doesn't support RETURNING *, so we need to manually fetch the created user.
            cursor.execute(
                'INSERT INTO "user" (user_id, sub, created_at) VALUES (?, ?, ?)',
                (str(uuid4()), sub, datetime.now()),
            )
            conn.commit()

            # Fetch the newly created user
            cursor.execute('SELECT * FROM "user" WHERE sub = ?', (sub,))
            new_user_row = cursor.fetchone()
            return User.model_validate(dict(new_user_row)), True

    async def delete_thread(self, user_id: str, thread_id: str):
        """Delete a thread by ID, including system threads."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM thread
                WHERE thread_id = ? AND (
                    user_id = ? 
                    OR user_id IN (
                        SELECT user_id 
                        FROM "user" 
                        WHERE sub LIKE 'tenant:%:system:system_user'
                    )
                )
                """,
                (thread_id, user_id),
            )
            conn.commit()

    async def delete_agent(self, user_id: str, agent_id: str) -> None:
        """Delete an agent by ID."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM agent WHERE id = ? AND user_id = ?",
                (agent_id, user_id),
            )
            conn.commit()

    async def get_agent_files(self, agent_id: str) -> list[UploadedFile]:
        """Get a list of files associated with an agent."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM file_owners
                WHERE agent_id = ?
                """,
                (agent_id,),
            )
            rows = cursor.fetchall()
            return UPLOADED_FILE_LIST_ADAPTER.validate_python(
                [dict(row) for row in rows]
            )

    async def get_thread_files(self, thread_id: str) -> list[UploadedFile]:
        """Get a list of files associated with a thread."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM file_owners
                WHERE thread_id = ?
                """,
                (thread_id,),
            )
            rows = cursor.fetchall()
            return UPLOADED_FILE_LIST_ADAPTER.validate_python(
                [dict(row) for row in rows]
            )

    async def get_file_by_id(self, file_id: str) -> Optional[UploadedFile]:
        """Get a file by id."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM file_owners
                WHERE file_id = ?
                """,
                (file_id,),
            )
            row = cursor.fetchone()
            return UploadedFile.model_validate(dict(row)) if row else None

    async def get_file(
        self, owner: Union[Agent, Thread], file_ref: str
    ) -> Optional[UploadedFile]:
        """Get a file by ref."""
        if isinstance(owner, Agent):
            query = "agent_id = ?"
            value = owner.id
        else:
            query = "thread_id = ?"
            value = owner.thread_id
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT * FROM file_owners
                WHERE file_ref = ?
                AND {query}
                """,
                (file_ref, value),
            )
            row = cursor.fetchone()
            return UploadedFile.model_validate(dict(row)) if row else None

    async def put_file_owner(
        self,
        file_id: str,
        file_path: Optional[str],
        file_ref: str,
        file_hash: str,
        embedded: bool,
        embedding_status: Optional[EmbeddingStatus],
        owner: Union[Agent, Thread],
        file_path_expiration: Optional[datetime],
    ) -> UploadedFile:
        if isinstance(owner, Agent):
            is_agent_file = True
            agent_id = owner.id
            thread_id = None
        else:
            is_agent_file = False
            agent_id = None
            thread_id = owner.thread_id
        new_uploaded_file = UploadedFile(
            file_id=file_id,
            file_path=file_path,
            file_ref=file_ref,
            file_hash=file_hash,
            embedded=embedded,
            embedding_status=embedding_status,
            file_path_expiration=file_path_expiration,
            agent_id=agent_id,
            thread_id=thread_id,
        )
        with self._connect() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    """
                    INSERT INTO file_owners (file_id, file_path, file_ref, file_hash, embedded, embedding_status, agent_id, thread_id, file_path_expiration)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    -- If a file with this file_id already exists, update with the new values instead of raising an error (override)
                    ON CONFLICT(file_id) DO UPDATE SET 
                        file_id = EXCLUDED.file_id,
                        file_path = EXCLUDED.file_path,
                        file_hash = EXCLUDED.file_hash,
                        embedded = EXCLUDED.embedded,
                        embedding_status = EXCLUDED.embedding_status,
                        agent_id = EXCLUDED.agent_id,
                        thread_id = EXCLUDED.thread_id,
                        file_path_expiration = EXCLUDED.file_path_expiration
                    """,
                    (
                        new_uploaded_file.file_id,
                        new_uploaded_file.file_path,
                        new_uploaded_file.file_ref,
                        new_uploaded_file.file_hash,
                        new_uploaded_file.embedded,
                        new_uploaded_file.embedding_status,
                        new_uploaded_file.agent_id,
                        new_uploaded_file.thread_id,
                        new_uploaded_file.file_path_expiration,
                    ),
                )
                conn.commit()
            except sqlite3.IntegrityError as e:
                is_constraint_unique_violation = (
                    e.sqlite_errorcode == sqlite3.SQLITE_CONSTRAINT_UNIQUE
                    and "file_owners.file_ref" in str(e)
                )

                if not is_constraint_unique_violation:
                    raise e
                else:
                    if is_agent_file:
                        # We need to check the current file: if it's already embedded, we can't override it!
                        cursor.execute(
                            "SELECT embedded FROM file_owners WHERE file_ref = ? AND agent_id = ?",
                            (file_ref, agent_id),
                        )
                        row = cursor.fetchone()
                        if row and row[0]:
                            raise UniqueFileRefError(file_ref)

                        cursor.execute(
                            """
                            UPDATE file_owners SET 
                            file_id = ?,
                            file_path = ?,
                            file_hash = ?,
                            embedded = ?,
                            embedding_status = ?,
                            thread_id = ?,
                            file_path_expiration = ?
                            WHERE file_ref = ? AND agent_id = ?
                            """,
                            (
                                file_id,
                                file_path,
                                file_hash,
                                embedded,
                                embedding_status,
                                thread_id,
                                file_path_expiration,
                                file_ref,
                                agent_id,
                            ),
                        )
                        conn.commit()
                    else:  # not is_agent_file:
                        # We need to check the current file: if it's already embedded, we can't override it!
                        cursor.execute(
                            "SELECT embedded FROM file_owners WHERE file_ref = ? AND thread_id = ?",
                            (file_ref, thread_id),
                        )
                        row = cursor.fetchone()
                        if row and row[0]:
                            raise UniqueFileRefError(file_ref)

                        cursor.execute(
                            """
                            UPDATE file_owners SET 
                            file_id = ?,
                            file_path = ?,
                            file_hash = ?,
                            embedded = ?,
                            embedding_status = ?,
                            agent_id = ?,
                            file_path_expiration = ?
                            WHERE file_ref = ? AND thread_id = ?
                            """,
                            (
                                file_id,
                                file_path,
                                file_hash,
                                embedded,
                                embedding_status,
                                agent_id,
                                file_path_expiration,
                                file_ref,
                                thread_id,
                            ),
                        )
                        conn.commit()
        return new_uploaded_file

    async def delete_file(self, file_id: str) -> None:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM file_owners WHERE file_id = ?", (file_id,))
            conn.commit()

    async def update_file_retrieve_information(
        self, file_id: str, *, file_path: str, file_path_expiration: datetime
    ) -> UploadedFile:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE file_owners
                SET file_path = ?, file_path_expiration = ?
                WHERE file_id = ?
                """,
                (file_path, file_path_expiration, file_id),
            )
            if cursor.rowcount == 0:
                raise ValueError(f"File with id {file_id} not found")

            # Fetch the updated row
            cursor.execute("SELECT * FROM file_owners WHERE file_id = ?", (file_id,))
            row = cursor.fetchone()
            conn.commit()

            return UploadedFile.model_validate(dict(row)) if row else None

    async def update_file_embedding_status(
        self, file_id: str, *, embedding_status: EmbeddingStatus
    ) -> None:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE file_owners
                SET embedding_status = ? 
                WHERE file_id = ?
                """,
                (embedding_status, file_id),
            )
            if cursor.rowcount == 0:
                raise ValueError(f"File with id {file_id} not found")
            conn.commit()

    async def create_async_run(self, run_id: str, status: str) -> None:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO async_runs (id, status) VALUES (?, ?)",
                (run_id, status),
            )
            conn.commit()

    async def update_async_run(self, run_id: str, status: str) -> None:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE async_runs SET status = ?  WHERE id = ?",
                (status, run_id),
            )
            conn.commit()

    async def get_async_run_status(self, run_id: str) -> Optional[str]:
        """Get run status"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status FROM async_runs WHERE id = ? ", (run_id,))
            row = cursor.fetchone()
            return row["status"] if row else None

    async def list_agent_threads(self, agent_id: str) -> List[Thread]:
        """List all threads for the current agent."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT t.* 
                FROM thread t
                WHERE t.agent_id = ?
                """,
                (agent_id,),
            )
            rows = cursor.fetchall()

            return THREAD_LIST_ADAPTER.validate_python([dict(row) for row in rows])

    async def get_system_user_id(self) -> str | None:
        """get the user_id of the system user"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT user_id FROM "user" WHERE sub LIKE "tenant:%%:system:system_user"'
            )
            if row := cursor.fetchone():
                return row["user_id"]
