import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

import asyncpg
import orjson
import structlog
from langchain_core.messages import AnyMessage
from pydantic import BaseModel, parse_obj_as

from sema4ai_agent_server.agent import get_agent_executor, runnable_agent
from sema4ai_agent_server.agent_types.constants import FINISH_NODE_KEY
from sema4ai_agent_server.schema import (
    MODEL,
    ActionPackage,
    Agent,
    AgentArchitecture,
    AgentMetadata,
    AgentReasoning,
    AgentStatus,
    Thread,
    UploadedFile,
    User,
    dummy_model,
)
from sema4ai_agent_server.storage import (
    BaseStorage,
    UniqueAgentNameError,
    basemodel_secret_encoder_for_db,
)

logger = structlog.get_logger()


UNIQUE_AGENT_NAME_CONSTRAINT_NAME = "idx_unique_agent_name"


def _json_encoder(v):
    if isinstance(v, BaseModel):
        return v.json(encoder=basemodel_secret_encoder_for_db)
    elif isinstance(v, list) and all(isinstance(i, BaseModel) for i in v):
        return json.dumps(
            [json.loads(i.json(encoder=basemodel_secret_encoder_for_db)) for i in v]
        )
    return orjson.dumps(v).decode()


def _json_decoder(v):
    return orjson.loads(v)


class PostgresStorage(BaseStorage):
    _pool: asyncpg.pool.Pool = None
    _is_setup: bool = False

    async def setup(self) -> None:
        if self._is_setup:
            return
        self._pool = await asyncpg.create_pool(
            database=os.environ["POSTGRES_DB"],
            user=os.environ["POSTGRES_USER"],
            password=os.environ["POSTGRES_PASSWORD"],
            host=os.environ["POSTGRES_HOST"],
            port=os.environ["POSTGRES_PORT"],
            init=self._init_connection,
        )
        await self._run_migrations()
        self._is_setup = True

    async def teardown(self) -> None:
        await self._pool.close()
        self._pool = None
        self._is_setup = False

    async def _init_connection(self, conn) -> None:
        await conn.set_type_codec(
            "json",
            encoder=_json_encoder,
            decoder=_json_decoder,
            schema="pg_catalog",
        )
        await conn.set_type_codec(
            "jsonb",
            encoder=_json_encoder,
            decoder=_json_decoder,
            schema="pg_catalog",
        )
        await conn.set_type_codec(
            "uuid", encoder=lambda v: str(v), decoder=lambda v: v, schema="pg_catalog"
        )

    def get_pool(self) -> asyncpg.pool.Pool:
        if not self._pool:
            raise Exception("Pool has not been created.")
        return self._pool

    async def list_all_agents(self) -> List[Agent]:
        async with self.get_pool().acquire() as conn:
            agents = await conn.fetch("SELECT * FROM agent ")
            return parse_obj_as(List[Agent], agents)

    async def agent_count(self) -> int:
        """Get agent row count"""
        async with self.get_pool().acquire() as conn:
            result = await conn.fetchrow("SELECT COUNT(*) FROM agent")
            count = result[0]
            return count

    async def thread_count(self) -> int:
        async with self.get_pool().acquire() as conn:
            result = await conn.fetchrow("SELECT COUNT(*) FROM thread")
            count = result[0]
            return count

    async def get_agent_files(self, agent_id: str) -> list[UploadedFile]:
        """Get a list of files associated with an agent."""
        async with self.get_pool().acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM file_owners WHERE agent_id = $1",
                agent_id,
            )
            return parse_obj_as(List[UploadedFile], rows)

    async def get_thread_files(self, thread_id: str) -> list[UploadedFile]:
        """Get a list of files associated with a thread."""
        async with self.get_pool().acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM file_owners WHERE thread_id = $1
                """,
                thread_id,
            )
            return parse_obj_as(List[UploadedFile], rows)

    async def get_file_by_id(self, file_id: str) -> Optional[UploadedFile]:
        """Get a file by id."""
        async with self.get_pool().acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM file_owners
                WHERE file_id = $1
                """,
                file_id,
            )
            return parse_obj_as(Optional[UploadedFile], row)

    async def get_file(
        self, owner: Union[Agent, Thread], file_ref: str
    ) -> Optional[UploadedFile]:
        """Get a file by ref."""
        if isinstance(owner, Agent):
            query = "agent_id = $2"
            value = owner.id
        else:
            query = "thread_id = $2"
            value = owner.thread_id
        async with self.get_pool().acquire() as conn:
            row = await conn.fetchrow(
                f"""
                SELECT * FROM file_owners
                WHERE file_ref = $1
                AND {query}
                """,
                file_ref,
                value,
            )
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
        async with self.get_pool().acquire() as conn:
            await conn.execute(
                """
                INSERT INTO file_owners (file_id, file_path, file_ref, file_hash, embedded, agent_id, thread_id, file_path_expiration)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT(file_id)
                DO UPDATE SET 
                    file_id = EXCLUDED.file_id,
                    file_path = EXCLUDED.file_path,
                    file_hash = EXCLUDED.file_hash,
                    embedded = EXCLUDED.embedded,
                    agent_id = EXCLUDED.agent_id,
                    thread_id = EXCLUDED.thread_id
                """,
                file_id,
                file_path,
                file_ref,
                file_hash,
                embedded,
                agent_id,
                thread_id,
                file_path_expiration,
            )
            return UploadedFile(
                file_id=file_id,
                file_path=file_path,
                file_ref=file_ref,
                file_hash=file_hash,
                embedded=embedded,
            )

    async def delete_file(self, file_id: str) -> None:
        async with self.get_pool().acquire() as conn:
            await conn.execute("DELETE FROM file_owners WHERE file_id = $1", file_id)

    async def _run_migrations(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        migrations_path = Path(current_dir).parent / "migrations" / "postgres"

        async with self.get_pool().acquire() as conn:
            # Check if migrations table exists and create it if it doesn't
            migrations_table_exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'migrations'
                );
                """
            )
            if not migrations_table_exists:
                await conn.execute(
                    """
                    CREATE TABLE migrations (
                        version BIGINT PRIMARY KEY, dirty BOOLEAN NOT NULL
                    );
                    """
                )
                await conn.execute(
                    "INSERT INTO migrations (version, dirty) VALUES (0, FALSE);"
                )

            dirty_version = await conn.fetchval(
                "SELECT version FROM migrations WHERE dirty = TRUE;"
            )
            if dirty_version:
                raise Exception(
                    f"Migration {dirty_version} is dirty. "
                    "No migrations will be applied. Please fix it manually."
                )

            current_version = await conn.fetchval("SELECT version FROM migrations;")
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
                    await conn.execute(
                        "UPDATE migrations SET version = $1, dirty = TRUE",
                        version,
                    )
                    # Try to apply the migration
                    with open(os.path.join(migrations_path, migration), "r") as f:
                        await conn.execute(f.read())
                    # Unset dirty flag
                    await conn.execute("UPDATE migrations SET dirty = FALSE")

                    current_version = version

    async def list_agents(self, user_id: str) -> List[Agent]:
        """List all agents for the current user."""
        async with self.get_pool().acquire() as conn:
            agents = await conn.fetch(
                "SELECT * FROM agent WHERE user_id = $1 OR public IS true", user_id
            )
            return parse_obj_as(List[Agent], agents)

    async def get_agent(self, user_id: str, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID."""
        async with self.get_pool().acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM agent WHERE id = $1 AND (user_id = $2 OR public IS true)",
                agent_id,
                user_id,
            )
            return parse_obj_as(Optional[Agent], row)

    async def put_agent(
        self,
        user_id: str,
        agent_id: str,
        *,
        public: bool,
        status: AgentStatus,
        name: str,
        description: str,
        runbook: str,
        version: str,
        model: MODEL,
        architecture: AgentArchitecture,
        reasoning: AgentReasoning,
        action_packages: list[ActionPackage],
        metadata: AgentMetadata,
    ) -> Agent:
        """Modify an agent."""
        updated_at = datetime.now(timezone.utc)
        conn = self.get_pool().acquire()
        async with self.get_pool().acquire() as conn:
            async with conn.transaction():
                try:
                    await conn.execute(
                        (
                            "INSERT INTO agent (id, user_id, public, status, name, description, runbook, version, model, architecture, reasoning, action_packages, updated_at, metadata) "
                            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14) "
                            "ON CONFLICT (id) DO UPDATE SET "
                            "user_id = EXCLUDED.user_id, "
                            "public = EXCLUDED.public, "
                            "status = EXCLUDED.status, "
                            "name = EXCLUDED.name, "
                            "description = EXCLUDED.description, "
                            "runbook = EXCLUDED.runbook, "
                            "version = EXCLUDED.version, "
                            "model = EXCLUDED.model, "
                            "architecture = EXCLUDED.architecture, "
                            "reasoning = EXCLUDED.reasoning, "
                            "action_packages = EXCLUDED.action_packages, "
                            "updated_at = EXCLUDED.updated_at, "
                            "metadata = EXCLUDED.metadata;"
                        ),
                        agent_id,
                        user_id,
                        public,
                        status,
                        name,
                        description,
                        runbook,
                        version,
                        model,
                        architecture,
                        reasoning,
                        action_packages,
                        updated_at,
                        metadata,
                    )
                except asyncpg.exceptions.UniqueViolationError as e:
                    if UNIQUE_AGENT_NAME_CONSTRAINT_NAME in str(e):
                        raise UniqueAgentNameError()
                    raise e
        return Agent(
            id=agent_id,
            user_id=user_id,
            public=public,
            status=status,
            name=name,
            description=description,
            runbook=runbook,
            version=version,
            model=model,
            architecture=architecture,
            reasoning=reasoning,
            action_packages=action_packages,
            updated_at=updated_at,
            metadata=metadata,
        )

    async def update_agent_status(
        self, user_id: str, agent_id: str, status: AgentStatus
    ) -> None:
        """Update the status of an agent."""
        async with self.get_pool().acquire() as conn:
            await conn.execute(
                "UPDATE agent SET status = $1 WHERE id = $2 AND user_id = $3",
                status,
                agent_id,
                user_id,
            )

    async def delete_agent(self, user_id: str, agent_id: str) -> None:
        """Delete an agent by ID."""
        async with self.get_pool().acquire() as conn:
            await conn.execute(
                "DELETE FROM agent WHERE id = $1 AND user_id = $2",
                agent_id,
                user_id,
            )

    async def list_threads(self, user_id: str) -> List[Thread]:
        """List all threads for the current user."""
        async with self.get_pool().acquire() as conn:
            threads = await conn.fetch(
                "SELECT * FROM thread WHERE user_id = $1", user_id
            )
            return parse_obj_as(List[Thread], threads)

    async def get_thread(self, user_id: str, thread_id: str) -> Optional[Thread]:
        """Get a thread by ID."""
        async with self.get_pool().acquire() as conn:
            thread = await conn.fetchrow(
                "SELECT * FROM thread WHERE thread_id = $1 AND user_id = $2",
                thread_id,
                user_id,
            )
            return parse_obj_as(Optional[Thread], thread)

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
        user_id: str,
        thread_id: str,
        values: Union[Sequence[AnyMessage], Dict[str, Any]],
        as_node: Optional[str] = FINISH_NODE_KEY,
    ):
        """Add state to a thread."""
        thread = await self.get_thread(user_id, thread_id)
        agent_id = thread.agent_id
        retval = runnable_agent.update_state(
            {"configurable": {"thread_id": thread_id, "agent_id": agent_id}},
            values,
            as_node=as_node,
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
        metadata: Optional[dict],
    ) -> Thread:
        """Modify a thread."""
        updated_at = datetime.now(timezone.utc)
        async with self.get_pool().acquire() as conn:
            await conn.execute(
                (
                    "INSERT INTO thread (thread_id, user_id, agent_id, name, updated_at, metadata) VALUES ($1, $2, $3, $4, $5, $6) "
                    "ON CONFLICT (thread_id) DO UPDATE SET "
                    "user_id = EXCLUDED.user_id,"
                    "agent_id = EXCLUDED.agent_id, "
                    "name = EXCLUDED.name, "
                    "updated_at = EXCLUDED.updated_at, "
                    "metadata = EXCLUDED.metadata;"
                ),
                thread_id,
                user_id,
                agent_id,
                name,
                updated_at,
                metadata,
            )
            return Thread(
                thread_id=thread_id,
                user_id=user_id,
                agent_id=agent_id,
                name=name,
                updated_at=updated_at,
                metadata=metadata,
            )

    async def delete_thread(self, user_id: str, thread_id: str):
        """Delete a thread by ID."""
        async with self.get_pool().acquire() as conn:
            await conn.execute(
                "DELETE FROM thread WHERE thread_id = $1 AND user_id = $2",
                thread_id,
                user_id,
            )

    async def get_or_create_user(self, sub: str) -> tuple[User, bool]:
        """Returns a tuple of the user and a boolean indicating whether the user was created."""
        async with self.get_pool().acquire() as conn:
            if user := await conn.fetchrow('SELECT * FROM "user" WHERE sub = $1', sub):
                return parse_obj_as(User, user), False
            user = await conn.fetchrow(
                'INSERT INTO "user" (sub) VALUES ($1) RETURNING *', sub
            )
            return parse_obj_as(User, user), True

    async def update_file_retrieve_information(
        self, file_id: str, *, file_path: str, file_path_expiration: datetime
    ) -> UploadedFile:
        async with self.get_pool().acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE file_owners
                SET file_path = $2, file_path_expiration = $3
                WHERE file_id = $1
                RETURNING *
                """,
                file_id,
                file_path,
                file_path_expiration,
            )
            if not row:
                raise ValueError(f"File with id {file_id} not found")
            return parse_obj_as(UploadedFile, row)

    async def create_async_run(self, run_id: str, status: str) -> None:
        async with self.get_pool().acquire() as conn:
            await conn.execute(
                "INSERT INTO async_runs (id, status) VALUES ($1, $2)", run_id, status
            )

    async def update_async_run(self, run_id: str, status: str) -> None:
        async with self.get_pool().acquire() as conn:
            await conn.execute(
                "UPDATE async_runs SET status = $2  WHERE id = $1", run_id, status
            )

    async def get_async_run_status(self, run_id: str) -> str:
        """Get run status"""
        async with self.get_pool().acquire() as conn:
            result = await conn.fetchrow(
                "SELECT status FROM async_runs WHERE id = $1", run_id
            )
            status = result[0]
            return status
