import json

import aiosqlite
from structlog import get_logger

from agent_server_types_v2.agent import Agent
from sema4ai_agent_server.storage.v2.errors_v2 import (
    AgentNotFoundError,
    AgentWithNameAlreadyExistsError,
    RecordAlreadyExistsError,
    ReferenceIntegrityError,
    UserAccessDeniedError,
)
from sema4ai_agent_server.storage.v2.sqlite_v2.common import CommonMixin


class SQLiteStorageAgentsMixin(CommonMixin):
    """
    Mixin providing SQLite-based agent operations.
    """

    _logger = get_logger(__name__)

    # -------------------------------------------------------------------------
    # Agents
    # -------------------------------------------------------------------------
    async def list_all_agents_v2(self) -> list[Agent]:
        """List all agents for all users."""
        async with self._cursor() as cur:
            await cur.execute("SELECT * FROM v2_agent")
            rows = await cur.fetchall()
        if not rows:
            return []
        return [Agent.from_dict(self._convert_agent_json_fields(dict(row))) for row in rows]

    async def list_agents_v2(self, user_id: str) -> list[Agent]:
        """List all agents for the given user."""
        self._validate_uuid(user_id)
        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT
                    a.*
                FROM v2_agent a
                WHERE v2_check_user_access(a.user_id, :user_id) = 1
                """,
                {"user_id": user_id},
            )
            rows = await cur.fetchall()
        if not rows:
            return []
        return [Agent.from_dict(self._convert_agent_json_fields(dict(row))) for row in rows]

    async def get_agent_v2(self, user_id: str, agent_id: str) -> Agent:
        """Get an agent by ID, raising errors if not found or no access."""
        self._validate_uuid(user_id)
        self._validate_uuid(agent_id)

        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT
                    a.*,
                    v2_check_user_access(a.user_id, :user_id) AS has_access
                FROM v2_agent a
                WHERE a.agent_id = :agent_id
                """,
                {"agent_id": agent_id, "user_id": user_id},
            )
            row = await cur.fetchone()

        if not row:
            # The agent does not exist at all
            raise AgentNotFoundError(f"Agent {agent_id} not found")

        if not row["has_access"]:
            # The agent exists but user does not have access
            raise UserAccessDeniedError(f"User {user_id} does not have access to agent {agent_id}")

        # Convert JSON columns and return
        row_dict = dict(row)
        row_dict.pop("has_access", None)
        return Agent.from_dict(self._convert_agent_json_fields(row_dict))

    async def get_agent_by_name_v2(self, user_id: str, name: str) -> Agent:
        """Get an agent by name."""
        self._validate_uuid(user_id)
        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT
                    a.*,
                    v2_check_user_access(a.user_id, :user_id) AS has_access
                FROM v2_agent a
                WHERE LOWER(a.name) = LOWER(:name)
                """,
                {"name": name, "user_id": user_id},
            )
            row = await cur.fetchone()

        if not row:
            raise AgentNotFoundError(f"Agent {name} not found")

        if not row["has_access"]:
            raise UserAccessDeniedError(f"User {user_id} does not have access to agent {name}")

        row_dict = dict(row)
        row_dict.pop("has_access", None)
        return Agent.from_dict(self._convert_agent_json_fields(row_dict))

    async def upsert_agent_v2(self, user_id: str, agent: Agent) -> None:
        """Create or update an agent, enforcing user access similar to Postgres."""
        self._validate_uuid(user_id)
        self._validate_uuid(agent.agent_id)

        # Convert the agent to a dict; JSON-ify the complex fields
        agent_dict = agent.to_json_dict() | {"user_id": user_id}
        for field in [
            "runbook",
            "action_packages",
            "agent_architecture",
            "question_groups",
            "observability_configs",
            "provider_configs",
            "extra",
        ]:
            agent_dict[field] = json.dumps(agent_dict[field])

        try:
            async with self._cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO v2_agent (
                        agent_id, name, description, user_id, runbook, version,
                        created_at, updated_at, action_packages, agent_architecture,
                        question_groups, observability_configs, provider_configs, extra, mode
                    )
                    VALUES (
                        :agent_id, :name, :description, :user_id, :runbook, :version,
                        :created_at, :updated_at, :action_packages, :agent_architecture,
                        :question_groups, :observability_configs, :provider_configs,
                        :extra, :mode
                    )
                    ON CONFLICT(agent_id) DO UPDATE SET
                        name = excluded.name,
                        description = excluded.description,
                        user_id = excluded.user_id,
                        runbook = excluded.runbook,
                        version = excluded.version,
                        updated_at = excluded.updated_at,
                        action_packages = excluded.action_packages,
                        agent_architecture = excluded.agent_architecture,
                        question_groups = excluded.question_groups,
                        observability_configs = excluded.observability_configs,
                        provider_configs = excluded.provider_configs,
                        extra = excluded.extra,
                        mode = excluded.mode
                    WHERE v2_check_user_access(v2_agent.user_id, :user_id) = 1
                    """,
                    agent_dict,
                )
                # If rowcount is 0 but the agent actually exists,
                # that typically means the user lacks permission
                if (
                    cur.rowcount == 0
                    and await self._agent_exists(agent.agent_id)
                    and await self._user_can_access_agent(user_id, agent.agent_id)
                    is False
                ):
                    raise UserAccessDeniedError(
                        f"User {user_id} does not have permission to update agent {agent.agent_id}",
                    )

        except aiosqlite.IntegrityError as e:
            if "foreign key constraint" in str(e).lower():
                raise ReferenceIntegrityError("Invalid foreign key reference updating agent") from e
            if "UNIQUE constraint failed: v2_agent.agent_id" in str(e):
                raise RecordAlreadyExistsError(f"Agent ID {agent.agent_id} is not unique") from e
            # Possibly triggered by a unique constraint on name, etc.
            self._logger.error("Error upserting agent", error=str(e), agent_id=agent.agent_id, user_id=user_id)
            raise AgentWithNameAlreadyExistsError(f"Agent name {agent.name} is not unique") from e

    async def delete_agent_v2(self, user_id: str, agent_id: str) -> None:
        """Delete an agent, enforcing user access."""
        self._validate_uuid(user_id)
        self._validate_uuid(agent_id)

        # First check if agent exists
        agent_exists = await self._agent_exists(agent_id)
        if not agent_exists:
            raise AgentNotFoundError(f"Agent {agent_id} not found")

        # Then check user access
        if not await self._user_can_access_agent(user_id, agent_id):
            raise UserAccessDeniedError(f"User {user_id} does not have access to agent {agent_id}")

        async with self._cursor() as cur:
            await cur.execute(
                """
                DELETE FROM v2_agent
                WHERE agent_id = :agent_id
                """,
                {"agent_id": agent_id},
            )

    async def count_agents_v2(self) -> int:
        """Count the number of agents."""
        async with self._cursor() as cur:
            await cur.execute("SELECT COUNT(*) AS cnt FROM v2_agent")
            row = await cur.fetchone()
        return row["cnt"] if row else 0

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    async def _agent_exists(self, agent_id: str) -> bool:
        """Helper to check if an agent with the given ID actually exists."""
        async with self._cursor() as cur:
            await cur.execute(
                "SELECT 1 FROM v2_agent WHERE agent_id = :agent_id LIMIT 1",
                {"agent_id": agent_id},
            )
            return bool(await cur.fetchone())

    async def _user_can_access_agent(self, user_id: str, agent_id: str) -> bool:
        """Helper to check if user has access to an agent."""
        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT v2_check_user_access(a.user_id, :user_id) AS has_access
                FROM v2_agent a
                WHERE a.agent_id = :agent_id
                """,
                {"agent_id": agent_id, "user_id": user_id},
            )
            row = await cur.fetchone()
        return bool(row and row["has_access"])

    def _convert_agent_json_fields(self, agent_dict: dict) -> dict:
        """Convert JSON string fields in agent dict to Python objects (similar to Postgres mixin)."""
        for field in [
            "runbook",
            "action_packages",
            "agent_architecture",
            "question_groups",
            "observability_configs",
            "provider_configs",
            "extra",
        ]:
            if agent_dict.get(field) is not None:
                agent_dict[field] = json.loads(agent_dict[field])
            else:
                agent_dict[field] = {}
        return agent_dict
