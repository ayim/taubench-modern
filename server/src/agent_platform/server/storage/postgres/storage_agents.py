from psycopg.errors import IntegrityError, UniqueViolation
from psycopg.types.json import Jsonb

from agent_platform.core.agent import Agent
from agent_platform.server.storage.errors import (
    AgentNotFoundError,
    AgentWithNameAlreadyExistsError,
    RecordAlreadyExistsError,
    UserAccessDeniedError,
)
from agent_platform.server.storage.postgres.common import CommonMixin


class PostgresStorageAgentsMixin(CommonMixin):
    """Mixin for PostgreSQL agent operations."""

    async def list_all_agents(self) -> list[Agent]:
        """List all agents for all users."""
        async with self._cursor() as cur:
            # 1. Get every agent
            await cur.execute("SELECT * FROM v2.agent")

            # 2. No agents found?
            if not (rows := await cur.fetchall()):
                return []

            # 3. Return all agents
            return [Agent.model_validate(row) for row in rows]

    async def list_agents(self, user_id: str) -> list[Agent]:
        """List all agents for the given user."""
        # 1. Validate the uuid
        self._validate_uuid(user_id)

        async with self._cursor() as cur:
            # 2. Get the agents (and check if the user has access)
            await cur.execute(
                """SELECT a.*
                   FROM v2.agent a
                   WHERE v2.check_user_access(a.user_id, %(user_id)s::uuid)""",
                {"user_id": user_id},
            )

            # 3. No agents found?
            if not (rows := await cur.fetchall()):
                return []

            # 4. Return the agents
            return [Agent.model_validate(row) for row in rows]

    async def get_agent(self, user_id: str, agent_id: str) -> Agent:
        """Get an agent by ID."""
        # 1. Validate the uuids
        self._validate_uuid(user_id)
        self._validate_uuid(agent_id)
        async with self._cursor() as cur:
            # 2. Get the agent (and check if the user has access)
            await cur.execute(
                """SELECT
                    a.*,
                    v2.check_user_access(a.user_id, %(user_id)s::uuid) as has_access
                   FROM v2.agent a
                   WHERE a.agent_id = %(agent_id)s::uuid""",
                {"agent_id": agent_id, "user_id": user_id},
            )

            # 3. No agent found?
            if not (row := await cur.fetchone()):
                raise AgentNotFoundError(f"Agent {agent_id} not found")

            # 4. User does not have access?
            if not row.pop("has_access"):
                raise UserAccessDeniedError(
                    f"User {user_id} does not have access to agent {agent_id}",
                )

            # 5. Return the agent
            return Agent.model_validate(row)

    async def get_agent_by_name(self, user_id: str, name: str) -> Agent:
        """Get an agent by name."""
        # 1. Validate the uuids
        self._validate_uuid(user_id)

        async with self._cursor() as cur:
            # 2. Get the agent (and check if the user has access)
            await cur.execute(
                """SELECT
                    a.*,
                    v2.check_user_access(a.user_id, %(user_id)s::uuid) as has_access
                   FROM v2.agent a
                   WHERE LOWER(a.name) = LOWER(%(name)s)""",
                {"name": name, "user_id": user_id},
            )

            # No agent found?
            if not (row := await cur.fetchone()):
                raise AgentNotFoundError(f"Agent {name} not found")

            # User does not have access?
            if not row.pop("has_access"):
                raise UserAccessDeniedError(
                    f"User {user_id} does not have access to agent {name}",
                )

            # Return the agent
            return Agent.model_validate(row)

    async def upsert_agent(self, user_id: str, agent: Agent) -> None:
        """Create or update an agent."""
        # 1. Validate the uuid
        self._validate_uuid(user_id)

        # 2. Convert the agent to a dictionary
        agent_dict = agent.model_dump() | {"user_id": user_id}

        # 3. Convert dict fields to Jsonb objects for proper PostgreSQL handling
        for field in ["runbook", "action_packages", "mcp_servers", "agent_architecture",
                    "question_groups", "observability_configs",
                    "platform_configs", "extra"]:
            agent_dict[field] = Jsonb(agent_dict[field])

        # 4. Insert the agent
        try:
            async with self._cursor() as cur:
                await cur.execute(
                    """INSERT INTO v2.agent
                    (agent_id, name, description, user_id, runbook, version,
                        created_at, updated_at, action_packages, mcp_servers,
                        agent_architecture, question_groups, observability_configs,
                        platform_configs, extra, mode)
                    VALUES (
                        %(agent_id)s::uuid, %(name)s, %(description)s,
                        %(user_id)s::uuid, %(runbook)s, %(version)s, %(created_at)s,
                        %(updated_at)s, %(action_packages)s, %(mcp_servers)s,
                        %(agent_architecture)s, %(question_groups)s,
                        %(observability_configs)s, %(platform_configs)s,
                        %(extra)s, %(mode)s
                    )
                    ON CONFLICT (agent_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        user_id = EXCLUDED.user_id,
                        runbook = EXCLUDED.runbook,
                        version = EXCLUDED.version,
                        updated_at = EXCLUDED.updated_at,
                        action_packages = EXCLUDED.action_packages,
                        mcp_servers = EXCLUDED.mcp_servers,
                        agent_architecture = EXCLUDED.agent_architecture,
                        question_groups = EXCLUDED.question_groups,
                        observability_configs = EXCLUDED.observability_configs,
                        platform_configs = EXCLUDED.platform_configs,
                        extra = EXCLUDED.extra,
                        mode = EXCLUDED.mode
                    WHERE v2.check_user_access(v2.agent.user_id, %(user_id)s::uuid)""",
                    agent_dict,
                )
        except UniqueViolation as e:
            raise AgentWithNameAlreadyExistsError(
                f"Agent name {agent.name} is not unique",
            ) from e
        except IntegrityError as e:
            if "UNIQUE constraint failed: v2.agent.agent_id" in str(e):
                raise RecordAlreadyExistsError(
                    f"Agent {agent.agent_id} already exists",
                ) from e
            raise

    async def delete_agent(self, user_id: str, agent_id: str) -> None:
        """Delete an agent."""
        # 1. Validate the uuids
        self._validate_uuid(user_id)
        self._validate_uuid(agent_id)

        async with self._cursor() as cur:
            # 2. Check if the user has access
            await cur.execute(
                """SELECT v2.check_user_access(a.user_id, %(user_id)s::uuid)
                   FROM v2.agent a
                   WHERE agent_id = %(agent_id)s::uuid""",
                {"agent_id": agent_id, "user_id": user_id},
            )

            # 3. User does not have access?
            if not (await cur.fetchone()):
                raise UserAccessDeniedError(
                    f"User {user_id} does not have access to agent {agent_id}",
                )

            # 4. User has access, delete the agent
            await cur.execute(
                """DELETE FROM v2.agent a
                   WHERE agent_id = %(agent_id)s::uuid""",
                {"agent_id": agent_id},
            )

    async def count_agents(self) -> int:
        """Count the number of agents."""
        async with self._cursor() as cur:
            # 1. Get the count
            await cur.execute("SELECT COUNT(*) FROM v2.agent")

            # 2. No results?
            if not (row := await cur.fetchone()):
                return 0

            # 3. Return the count
            return row["count"]
