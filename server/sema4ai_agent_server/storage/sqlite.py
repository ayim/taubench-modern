import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union
from uuid import uuid4

import structlog
from langchain_core.messages import AnyMessage
from pydantic import parse_obj_as

from sema4ai_agent_server.agent import AgentType, runnable_agent, get_agent_executor
from sema4ai_agent_server.agent_types.constants import FINISH_NODE_KEY
from sema4ai_agent_server.constants import DOMAIN_DATABASE_PATH
from sema4ai_agent_server.schema import Agent, Thread, UploadedFile, User
from sema4ai_agent_server.storage import BaseStorage

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
        conn = sqlite3.connect(DOMAIN_DATABASE_PATH)
        conn.row_factory = sqlite3.Row  # Enable dictionary access to row items.
        try:
            yield conn
        finally:
            conn.close()

    async def _run_migrations(self):
        db_exists = os.path.exists(DOMAIN_DATABASE_PATH)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        migrations_path = Path(current_dir).parent / "migrations" / "sqlite"

        with self._connect() as conn:
            cursor = conn.cursor()

            current_version = 0
            if db_exists:
                # Check if migration_version table exists
                cursor.execute(
                    """
                    SELECT name FROM sqlite_master WHERE type='table' AND name='migration_version';
                """
                )
                if cursor.fetchone() is None:
                    # Migration table does not exist, assume version 3
                    current_version = 0
                else:
                    # Get the current migration version
                    cursor.execute(
                        "SELECT MAX(version) AS version FROM migration_version;"
                    )
                    current_version = cursor.fetchone()["version"]

            # List and sort migration files
            migration_files = sorted(
                (f for f in os.listdir(migrations_path) if f.endswith(".up.sql")),
                key=lambda x: int(x.split("_")[0]),
            )

            logger.info(f"Migrations found: {migration_files}")
            logger.info(f"Current migration version: {current_version}")

            # Apply migrations that are newer than the current version
            for migration in migration_files:
                version = int(migration.split("_")[0])
                if version > current_version:
                    logger.info(f"Applying migration {migration}")
                    with open(os.path.join(migrations_path, migration), "r") as f:
                        conn.executescript(f.read())
                        current_version = (
                            version  # Update current version after successful migration
                        )
            cursor.execute(
                "INSERT INTO migration_version (version) VALUES (?);", (version,)
            )
            conn.commit()

    async def list_agents(self, user_id: str) -> List[Agent]:
        """List all agents for the current user."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row  # Enable dictionary-like row access
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM agent WHERE user_id = ?", (user_id,))
            rows = cursor.fetchall()

            # Deserialize the 'config' field from a JSON string to a dict for each row
            agents = []
            for row in rows:
                agent_data = dict(row)  # Convert sqlite3.Row to dict
                agent_data["config"] = (
                    json.loads(agent_data["config"])
                    if "config" in agent_data and agent_data["config"]
                    else {}
                )
                agent_data["metadata"] = (
                    json.loads(agent_data["metadata"])
                    if agent_data["metadata"] is not None
                    else None
                )
                agent = Agent(**agent_data)
                agents.append(agent)

            return agents

    async def list_all_agents(self) -> List[Agent]:
        """List all agents for all users."""
        with self._connect() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM agent")
            rows = cursor.fetchall()

            agents = []
            for row in rows:
                agent_data = dict(row)
                agent_data["config"] = (
                    json.loads(agent_data["config"])
                    if "config" in agent_data and agent_data["config"]
                    else {}
                )
                agent_data["metadata"] = (
                    json.loads(agent_data["metadata"])
                    if agent_data["metadata"] is not None
                    else None
                )
                agent = Agent(**agent_data)
                agents.append(agent)

            return agents

    async def get_agent(
        self, user_id: str, agent_id: str
    ) -> Optional[Agent]:
        """Get an agent by ID."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM agent WHERE id = ? AND (user_id = ? OR public = 1)",
                (agent_id, user_id),
            )
            row = cursor.fetchone()
            if not row:
                return None
            agent_data = dict(row)  # Convert sqlite3.Row to dict
            agent_data["config"] = (
                json.loads(agent_data["config"])
                if "config" in agent_data and agent_data["config"]
                else {}
            )
            agent_data["metadata"] = (
                json.loads(agent_data["metadata"])
                if agent_data["metadata"] is not None
                else None
            )
            return Agent(**agent_data)

    async def put_agent(
        self,
        user_id: str,
        agent_id: str,
        *,
        name: str,
        config: dict,
        public: bool = False,
        metadata: Optional[dict],
    ) -> Agent:
        """Modify an agent."""
        updated_at = datetime.now(timezone.utc)
        with self._connect() as conn:
            cursor = conn.cursor()
            # Convert the config dict to a JSON string for storage.
            config_str = json.dumps(config)
            cursor.execute(
                """
                INSERT INTO agent (id, user_id, name, config, updated_at, public, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) 
                DO UPDATE SET 
                    user_id = EXCLUDED.user_id, 
                    name = EXCLUDED.name, 
                    config = EXCLUDED.config, 
                    updated_at = EXCLUDED.updated_at, 
                    public = EXCLUDED.public,
                    metadata = EXCLUDED.metadata
                """,
                (
                    agent_id,
                    user_id,
                    name,
                    config_str,
                    updated_at.isoformat(),
                    public,
                    json.dumps(metadata),
                ),
            )
            conn.commit()
            return Agent(
                id=agent_id,
                user_id=user_id,
                name=name,
                config=config,
                updated_at=updated_at,
                public=public,
                metadata=metadata,
            )

    async def agent_count(self) -> int:
        """Get agent row count"""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM agent")
            count = cursor.fetchone()[0]
            return count

    async def list_threads(self, user_id: str) -> List[Thread]:
        """List all threads for the current user."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM thread WHERE user_id = ?", (user_id,))
            rows = cursor.fetchall()
            threads = []
            for row in rows:
                thread_data = dict(row)
                thread_data["metadata"] = (
                    json.loads(thread_data["metadata"])
                    if thread_data["metadata"] is not None
                    else None
                )
                thread = Thread(**thread_data)
                threads.append(thread)
            return threads

    async def get_thread(self, user_id: str, thread_id: str) -> Optional[Thread]:
        """Get a thread by ID."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM thread WHERE thread_id = ? AND user_id = ?",
                (thread_id, user_id),
            )
            row = cursor.fetchone()
            if not row:
                return None
            thread_data = dict(row)
            thread_data["metadata"] = (
                json.loads(thread_data["metadata"])
                if thread_data["metadata"] is not None
                else None
            )
            return Thread(**thread_data)

    async def thread_count(self) -> int:
        """Get thread row count."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM thread")
            count = cursor.fetchone()[0]
            return count

    async def get_thread_state(self, user_id: str, thread_id: str):
        """Get state for a thread."""
        app = get_agent_executor([], AgentType.GPT_35_TURBO, "", "", False, 0, None)
        state = app.get_state({"configurable": {"thread_id": thread_id}})
        return {
            "values": state.values,
            "next": state.next,
        }

    async def update_thread_state(
        self,
        user_id: str,
        thread_id: str,
        values: Union[Sequence[AnyMessage], Dict[str, Any]],
        as_node: Optional[str] = FINISH_NODE_KEY,
    ):
        """Add state to a thread."""
        thread = await self.get_thread(user_id, thread_id)
        agent_id = thread.agent_id
        agent = await self.get_agent(user_id, agent_id)
        config = agent.config["configurable"] if agent else {}
        retval = runnable_agent.update_state(
            {
                "configurable": {
                    **config,
                    "thread_id": thread_id,
                    "agent_id": agent_id,
                }
            },
            values,
            as_node=as_node,
        )
        return retval

    async def get_thread_history(self, user_id: str, thread_id: str):
        """Get the history of a thread."""
        app = get_agent_executor([], AgentType.GPT_35_TURBO, "", "", False, None)
        return [
            {
                "values": c.values,
                "next": c.next,
                "config": c.config,
                "parent": c.parent_config,
            }
            for c in app.get_state_history({"configurable": {"thread_id": thread_id}})
        ]

    async def put_thread(
        self,
        user_id: str,
        thread_id: str,
        *,
        agent_id: str,
        name: str,
        metadata: Optional[dict],
    ) -> Thread:
        """Modify a thread."""
        updated_at = datetime.now(timezone.utc)
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO thread (thread_id, user_id, agent_id, name, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(thread_id) 
                DO UPDATE SET 
                    user_id = EXCLUDED.user_id,
                    agent_id = EXCLUDED.agent_id, 
                    name = EXCLUDED.name, 
                    updated_at = EXCLUDED.updated_at,
                    metadata = EXCLUDED.metadata
                """,
                (
                    thread_id,
                    user_id,
                    agent_id,
                    name,
                    updated_at,
                    json.dumps(metadata),
                ),
            )
            conn.commit()
            return Thread(
                thread_id=thread_id,
                user_id=user_id,
                agent_id=agent_id,
                name=name,
                updated_at=updated_at,
                metadata=metadata,
            )

    async def get_or_create_user(self, sub: str) -> tuple[User, bool]:
        """Returns a tuple of the user and a boolean indicating whether the user was created."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM "user" WHERE sub = ?', (sub,))
            user_row = cursor.fetchone()

            if user_row:
                return parse_obj_as(User, user_row), False

            # SQLite doesn't support RETURNING *, so we need to manually fetch the created user.
            cursor.execute(
                'INSERT INTO "user" (user_id, sub, created_at) VALUES (?, ?, ?)',
                (str(uuid4()), sub, datetime.now()),
            )
            conn.commit()

            # Fetch the newly created user
            cursor.execute('SELECT * FROM "user" WHERE sub = ?', (sub,))
            new_user_row = cursor.fetchone()
            return parse_obj_as(User, new_user_row), True

    async def delete_thread(self, user_id: str, thread_id: str):
        """Delete a thread by ID."""
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM thread WHERE thread_id = ? AND user_id = ?",
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
            return parse_obj_as(List[UploadedFile], rows)

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
            return parse_obj_as(List[UploadedFile], rows)

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
            return parse_obj_as(Optional[UploadedFile], row)

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
            return parse_obj_as(Optional[UploadedFile], row)

    async def put_file_owner(
        self,
        file_id: str,
        file_path: Optional[str],
        file_ref: str,
        file_hash: str,
        embedded: bool,
        owner: Union[Agent, Thread],
        file_path_expiration: Optional[datetime],
    ) -> UploadedFile:
        if isinstance(owner, Agent):
            agent_id = owner.id
            thread_id = None
        else:
            agent_id = None
            thread_id = owner.thread_id
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO file_owners (file_id, file_path, file_ref, file_hash, embedded, agent_id, thread_id, file_path_expiration)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(file_id)
                DO UPDATE SET 
                    file_id = EXCLUDED.file_id,
                    file_path = EXCLUDED.file_path,
                    file_hash = EXCLUDED.file_hash,
                    embedded = EXCLUDED.embedded,
                    agent_id = EXCLUDED.agent_id,
                    thread_id = EXCLUDED.thread_id
                """,
                (
                    file_id,
                    file_path,
                    file_ref,
                    file_hash,
                    embedded,
                    agent_id,
                    thread_id,
                    file_path_expiration,
                ),
            )
            conn.commit()
            return UploadedFile(
                file_id=file_id,
                file_path=file_path,
                file_ref=file_ref,
                file_hash=file_hash,
                embedded=embedded,
            )

    async def delete_file(self, file_id: str) -> None:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM file_owners WHERE file_id = ?", (file_id,))
            conn.commit()
