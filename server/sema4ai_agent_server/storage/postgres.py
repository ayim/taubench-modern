import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Sequence, Union

import structlog
from langchain_core.messages import AnyMessage
from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row

from sema4ai_agent_server.agent import get_agent_executor, runnable_agent
from sema4ai_agent_server.agent_types.constants import FINISH_NODE_KEY
from sema4ai_agent_server.schema import (
    AGENT_LIST_ADAPTER,
    MODEL,
    RAW_CONTEXT,
    THREAD_LIST_ADAPTER,
    UPLOADED_FILE_LIST_ADAPTER,
    ActionPackage,
    Agent,
    AgentAdvancedConfig,
    AgentMetadata,
    AgentReasoning,
    EmbeddingStatus,
    Thread,
    UploadedFile,
    User,
    dummy_model,
)
from sema4ai_agent_server.storage import (
    BaseStorage,
    UniqueAgentNameError,
    UniqueFileRefError,
)
from sema4ai_agent_server.storage.embed import get_vector_store
from sema4ai_agent_server.storage.postgres_conn import PostgresConnectionManager
from sema4ai_agent_server.storage.utils import model_dump_for_postgres
from sema4ai_agent_server.storage.vectorstore import PostgresVector

logger = structlog.get_logger()


UNIQUE_AGENT_NAME_CONSTRAINT_NAME = "idx_unique_agent_name"
UNIQUE_FILE_REF_AGENT_CONSTRAINT_NAME = "unique_file_ref_agent"
UNIQUE_FILE_REF_THREAD_CONSTRAINT_NAME = "unique_file_ref_thread"


class PostgresStorage(BaseStorage, PostgresConnectionManager):
    # TODO: Consider using Pydantic models as row factories when appropriate, see
    # https://www.psycopg.org/psycopg3/docs/advanced/typing.html#example-returning-records-as-pydantic-models
    _is_setup: bool = False

    async def setup(self) -> None:
        if self._is_setup:
            return
        await self._run_migrations()
        pgvector: PostgresVector = get_vector_store()
        await pgvector.acreate_collection()
        self._is_setup = True

    async def teardown(self) -> None:
        self._is_setup = False

    async def list_all_agents(self) -> List[Agent]:
        async with self.async_cursor(dict_row) as cur:
            await cur.execute("SELECT * FROM agent ")
            rows = await cur.fetchall()
            return AGENT_LIST_ADAPTER.validate_python(rows)

    async def agent_count(self) -> int:
        """Get agent row count"""
        async with self.async_cursor() as cur:
            await cur.execute("SELECT COUNT(*) FROM agent")
            result = await cur.fetchone()
            return result[0]

    async def thread_count(self) -> int:
        async with self.async_cursor() as cur:
            await cur.execute("SELECT COUNT(*) FROM thread")
            result = await cur.fetchone()
            return result[0]

    async def get_agent_files(self, agent_id: str) -> list[UploadedFile]:
        """Get a list of files associated with an agent."""
        async with self.async_cursor(dict_row) as cur:
            await cur.execute(
                "SELECT * FROM file_owners WHERE agent_id = %s", (agent_id,)
            )
            rows = await cur.fetchall()
            return UPLOADED_FILE_LIST_ADAPTER.validate_python(rows)

    async def get_thread_files(self, thread_id: str) -> list[UploadedFile]:
        """Get a list of files associated with a thread."""
        async with self.async_cursor(dict_row) as cur:
            await cur.execute(
                """
                SELECT * FROM file_owners WHERE thread_id = %s
                """,
                (thread_id,),
            )
            rows = await cur.fetchall()
            return UPLOADED_FILE_LIST_ADAPTER.validate_python(rows)

    async def get_file_by_id(self, file_id: str) -> UploadedFile | None:
        """Get a file by id."""
        async with self.async_cursor(dict_row) as cur:
            await cur.execute(
                "SELECT * FROM file_owners WHERE file_id = %s", (file_id,)
            )
            row = await cur.fetchone()
            if not row:
                return None
            return UploadedFile.model_validate(row)

    async def get_file(
        self, owner: Union[Agent, Thread], file_ref: str
    ) -> UploadedFile | None:
        """Get a file by ref."""
        if isinstance(owner, Agent):
            query = "agent_id = %s"
            value = owner.id
        else:
            query = "thread_id = %s"
            value = owner.thread_id
        async with self.async_cursor(dict_row) as cur:
            await cur.execute(
                f"""
                SELECT * FROM file_owners
                WHERE file_ref = %s
                AND {query}
                """,
                (
                    file_ref,
                    value,
                ),
            )
            row = await cur.fetchone()
            if not row:
                return None
            return UploadedFile.model_validate(row)

    async def put_file_owner(
        self,
        file_id: str,
        file_path: str | None,
        file_ref: str,
        file_hash: str,
        embedded: bool,
        embedding_status: EmbeddingStatus | None,
        owner: Union[Agent, Thread],
        file_path_expiration: datetime | None,
    ) -> UploadedFile:
        if isinstance(owner, Agent):
            agent_id = owner.id
            thread_id = None
        else:
            agent_id = None
            thread_id = owner.thread_id
        new_file = UploadedFile(
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
        async with self.async_cursor() as cur:
            try:
                await cur.execute(
                    """
                    INSERT INTO file_owners (
                        file_id, file_path, file_ref, file_hash, embedded, embedding_status, agent_id,
                        thread_id, file_path_expiration
                    ) VALUES (
                        %(file_id)s, %(file_path)s, %(file_ref)s, %(file_hash)s, %(embedded)s,
                        %(embedding_status)s, %(agent_id)s, %(thread_id)s, %(file_path_expiration)s
                    ) ON CONFLICT(file_id)
                    DO UPDATE SET 
                        file_id = EXCLUDED.file_id,
                        file_path = EXCLUDED.file_path,
                        file_hash = EXCLUDED.file_hash,
                        embedded = EXCLUDED.embedded,
                        embedding_status = EXCLUDED.embedding_status,
                        agent_id = EXCLUDED.agent_id,
                        thread_id = EXCLUDED.thread_id,
                        file_path_expiration = EXCLUDED.file_path_expiration
                    """,
                    model_dump_for_postgres(new_file, context=RAW_CONTEXT),
                )
            except UniqueViolation as e:
                if UNIQUE_FILE_REF_AGENT_CONSTRAINT_NAME in str(
                    e
                ) or UNIQUE_FILE_REF_THREAD_CONSTRAINT_NAME in str(e):
                    raise UniqueFileRefError(file_ref)
                raise e

            return new_file

    async def delete_file(self, file_id: str) -> None:
        async with self.async_cursor() as cur:
            await cur.execute("DELETE FROM file_owners WHERE file_id = %s", (file_id,))

    async def _run_migrations(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        migrations_path = Path(current_dir).parent / "migrations" / "postgres"

        async with self.async_cursor() as cur:
            # Check if migrations table exists and create it if it doesn't
            await cur.execute(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'migrations'
                );
                """
            )
            results = await cur.fetchone()
            migrations_table_exists = results[0] if results else False
            if not migrations_table_exists:
                await cur.execute(
                    """
                    CREATE TABLE migrations (
                        version BIGINT PRIMARY KEY, dirty BOOLEAN NOT NULL
                    );
                    """
                )
                await cur.execute(
                    "INSERT INTO migrations (version, dirty) VALUES (0, FALSE);"
                )

            await cur.execute("SELECT version FROM migrations WHERE dirty = TRUE;")
            results = await cur.fetchone()
            dirty_version = results[0] if results else None
            if dirty_version:
                raise Exception(
                    f"Migration {dirty_version} is dirty. "
                    "No migrations will be applied. Please fix it manually."
                )

            await cur.execute("SELECT version FROM migrations;")
            results = await cur.fetchone()
            current_version = results[0] if results else 0
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
                    await cur.execute(
                        "UPDATE migrations SET version = %s, dirty = TRUE", (version,)
                    )
                    # Try to apply the migration
                    with open(os.path.join(migrations_path, migration), "r") as f:
                        await cur.execute(f.read())
                    # Unset dirty flag
                    await cur.execute("UPDATE migrations SET dirty = FALSE")

                    current_version = version

    async def list_agents(self, user_id: str) -> List[Agent]:
        """List all agents for the current user."""
        async with self.async_cursor(dict_row) as cur:
            await cur.execute(
                "SELECT * FROM agent WHERE user_id = %s OR public IS true", (user_id,)
            )
            rows = await cur.fetchall()
            return AGENT_LIST_ADAPTER.validate_python(rows)

    async def get_agent(self, user_id: str, agent_id: str) -> Agent | None:
        """Get an agent by ID."""
        async with self.async_cursor(dict_row) as cur:
            await cur.execute(
                "SELECT * FROM agent WHERE id = %s AND (user_id = %s OR public IS true)",
                (
                    agent_id,
                    user_id,
                ),
            )
            row = await cur.fetchone()
            return Agent.model_validate(row) if row else None

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
        async with self.async_cursor() as cur:
            try:
                await cur.execute(
                    """
                    INSERT INTO agent (
                        id, user_id, public, name, description, runbook, version, model, 
                        advanced_config, action_packages, updated_at, metadata, created_at
                    ) VALUES (
                        %(id)s, %(user_id)s, %(public)s, %(name)s, %(description)s, %(runbook)s,
                        %(version)s, %(model)s, %(advanced_config)s, %(action_packages)s,
                        %(updated_at)s, %(metadata)s, %(created_at)s
                    ) ON CONFLICT (id) DO UPDATE SET
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
                        created_at = EXCLUDED.created_at;
                    """,
                    model_dump_for_postgres(new_agent, context=RAW_CONTEXT),
                )
            except UniqueViolation as e:
                if UNIQUE_AGENT_NAME_CONSTRAINT_NAME in str(e):
                    raise UniqueAgentNameError(name)
                raise e
        return new_agent

    async def delete_agent(self, user_id: str, agent_id: str) -> None:
        """Delete an agent by ID."""
        async with self.async_cursor() as cur:
            await cur.execute(
                "DELETE FROM agent WHERE id = %s AND user_id = %s",
                (
                    agent_id,
                    user_id,
                ),
            )

    async def list_threads(self, user_id: str) -> List[Thread]:
        """List all threads for the current user and system threads."""
        async with self.async_cursor(dict_row) as cur:
            await cur.execute(
                """
                SELECT t.* 
                FROM thread t
                LEFT JOIN "user" u ON t.user_id = u.user_id
                WHERE t.user_id = %s OR u.sub LIKE 'tenant:%%:system:system_user'
                """,
                (user_id,),
            )
            rows = await cur.fetchall()
            return THREAD_LIST_ADAPTER.validate_python(rows)

    async def get_thread(self, user_id: str, thread_id: str) -> Thread | None:
        """Get a thread by ID, including system threads."""
        async with self.async_cursor(dict_row) as cur:
            await cur.execute(
                """
                SELECT t.* 
                FROM thread t
                LEFT JOIN "user" u ON t.user_id = u.user_id
                WHERE t.thread_id = %s AND (t.user_id = %s OR u.sub LIKE 'tenant:%%:system:system_user')
                """,
                (
                    thread_id,
                    user_id,
                ),
            )
            row = await cur.fetchone()
            return Thread.model_validate(row) if row else None

    async def get_thread_state(self, thread_id: str):
        """Get state for a thread."""
        app = get_agent_executor(
            [], dummy_model, "", "", False, AgentReasoning.DISABLED, None
        )
        state = app.get_state({"configurable": {"thread_id": thread_id}})
        return {
            "values": state.values,
            "next": state.next,
        }

    async def update_thread_state(
        self,
        thread_id: str,
        values: Union[Sequence[AnyMessage], Dict[str, Any]],
        as_node: str | None = FINISH_NODE_KEY,
    ):
        """Add state to a thread."""
        retval = runnable_agent.update_state(
            {"configurable": {"thread_id": thread_id}}, values, as_node=as_node
        )
        return retval

    async def get_thread_history(self, thread_id: str):
        """Get the history of a thread."""
        app = get_agent_executor(
            [], dummy_model, "", "", False, AgentReasoning.DISABLED, None
        )

        history = []
        for c in app.get_state_history({"configurable": {"thread_id": thread_id}}):
            history.append(
                {
                    "values": c.values,
                    "next": c.next,
                    "config": c.config,
                    "parent": c.parent_config,
                }
            )

        return history

    async def put_thread(
        self,
        user_id: str,
        thread_id: str,
        *,
        agent_id: str,
        name: str,
        metadata: dict | None,
        created_at: datetime,
    ) -> Thread:
        """Modify a thread."""
        updated_at = datetime.now(timezone.utc)
        new_thread = Thread(
            thread_id=thread_id,
            user_id=user_id,
            agent_id=agent_id,
            name=name,
            created_at=created_at,
            updated_at=updated_at,
            metadata=metadata,
        )
        async with self.async_cursor() as cur:
            await cur.execute(
                """
                INSERT INTO thread (
                    thread_id, user_id, agent_id, name, updated_at, metadata, created_at
                ) VALUES (
                    %(thread_id)s, %(user_id)s, %(agent_id)s, %(name)s, %(updated_at)s,
                    %(metadata)s, %(created_at)s
                ) ON CONFLICT (thread_id) DO UPDATE SET
                    user_id = EXCLUDED.user_id,
                    agent_id = EXCLUDED.agent_id,
                    name = EXCLUDED.name,
                    updated_at = EXCLUDED.updated_at,
                    metadata = EXCLUDED.metadata,
                    created_at = EXCLUDED.created_at;
                """,
                model_dump_for_postgres(new_thread, context=RAW_CONTEXT),
            )
            return new_thread

    async def delete_thread(self, user_id: str, thread_id: str):
        """Delete a thread by ID, including system threads."""
        async with self.async_cursor() as cur:
            await cur.execute(
                """
                DELETE FROM thread
                WHERE thread_id = %s AND (
                    user_id = %s 
                    OR user_id IN (
                        SELECT user_id 
                        FROM "user" 
                        WHERE sub LIKE 'tenant:%%:system:system_user'
                    )
                )
                """,
                (
                    thread_id,
                    user_id,
                ),
            )

    async def get_or_create_user(self, sub: str) -> tuple[User, bool]:
        """Returns a tuple of the user and a boolean indicating whether the user was created."""
        async with self.async_cursor(dict_row) as cur:
            await cur.execute('SELECT * FROM "user" WHERE sub = %s', (sub,))
            if row := await cur.fetchone():
                return User.model_validate(row), False
            await cur.execute(
                'INSERT INTO "user" (sub) VALUES (%s) RETURNING *', (sub,)
            )
            row = await cur.fetchone()
            return User.model_validate(row), True

    async def update_file_retrieve_information(
        self, file_id: str, *, file_path: str, file_path_expiration: datetime
    ) -> UploadedFile:
        async with self.async_cursor(dict_row) as cur:
            await cur.execute(
                """
                UPDATE file_owners
                SET file_path = %s, file_path_expiration = %s
                WHERE file_id = %s
                RETURNING *;
                """,
                (
                    file_id,
                    file_path,
                    file_path_expiration,
                ),
            )
            row = await cur.fetchone()
            if not row:
                raise ValueError(f"File with id {file_id} not found")
            return UploadedFile.model_validate(row)

    async def update_file_embedding_status(
        self, file_id: str, *, embedding_status: EmbeddingStatus
    ) -> None:
        async with self.async_cursor() as cur:
            await cur.execute(
                """
                UPDATE file_owners
                SET embedding_status = %s 
                WHERE file_id = %s
                """,
                (
                    embedding_status,
                    file_id,
                ),
            )
            if cur.rowcount == 0:
                raise ValueError(f"File with id {file_id} not found")

    async def create_async_run(self, run_id: str, status: str) -> None:
        async with self.async_cursor() as cur:
            await cur.execute(
                "INSERT INTO async_runs (id, status) VALUES (%s, %s);", (run_id, status)
            )

    async def update_async_run(self, run_id: str, status: str) -> None:
        async with self.async_cursor() as cur:
            await cur.execute(
                "UPDATE async_runs SET status = %s  WHERE id = %s", (status, run_id)
            )

    async def get_async_run_status(self, run_id: str) -> str:
        """Get run status"""
        async with self.async_cursor() as cur:
            await cur.execute("SELECT status FROM async_runs WHERE id = %s", (run_id,))
            result = await cur.fetchone()
            return result[0]

    async def list_agent_threads(self, agent_id: str) -> List[Thread]:
        """List all threads for the current agent."""
        async with self.async_cursor(dict_row) as cur:
            await cur.execute(
                """
                SELECT t.* 
                FROM thread t
                WHERE t.agent_id = %s
                """,
                (agent_id,),
            )
            rows = await cur.fetchall()
            return THREAD_LIST_ADAPTER.validate_python(rows)

    async def get_system_user_id(self) -> str | None:
        """get the user_id of the system user"""
        async with self.async_cursor(dict_row) as cur:
            await cur.execute(
                """SELECT * FROM "user" WHERE sub LIKE 'tenant:%%:system:system_user'"""
            )
            if row := await cur.fetchone():
                return row["user_id"]
