from psycopg.errors import IntegrityError
from psycopg.types.json import Jsonb

from agent_platform.core.agent import Agent
from agent_platform.server.storage.common import CommonMixin
from agent_platform.server.storage.errors import (
    AgentNotFoundError,
    AgentWithNameAlreadyExistsError,
    RecordAlreadyExistsError,
    UserAccessDeniedError,
)
from agent_platform.server.storage.postgres.cursor import CursorMixin


class PostgresStorageAgentsMixin(CursorMixin, CommonMixin):
    """Mixin for PostgreSQL agent operations."""

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
        """Create or update an agent, avoiding false-positives on
        the name-uniqueness index."""
        # 1. Validate uuids
        self._validate_uuid(user_id)
        self._validate_uuid(agent.agent_id)

        # 2. Build a dict and wrap JSON fields in Jsonb
        agent_dict = agent.model_dump() | {"user_id": user_id}
        for field in [
            "runbook_structured",
            "action_packages",
            "mcp_servers",
            "agent_architecture",
            "question_groups",
            "observability_configs",
            "platform_configs",
            "extra",
        ]:
            agent_dict[field] = Jsonb(agent_dict[field])

        # 3. Insert/update the agent
        try:
            async with self._cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO v2.agent (
                      agent_id, name, description, user_id, runbook_structured,
                      version, created_at, updated_at, action_packages,
                      mcp_servers, agent_architecture, question_groups,
                      observability_configs, platform_configs, extra, mode
                    )
                    VALUES (
                      %(agent_id)s::uuid, %(name)s, %(description)s,
                      %(user_id)s::uuid, %(runbook_structured)s, %(version)s,
                      %(created_at)s, %(updated_at)s, %(action_packages)s,
                      %(mcp_servers)s, %(agent_architecture)s, %(question_groups)s,
                      %(observability_configs)s, %(platform_configs)s,
                      %(extra)s, %(mode)s
                    )
                    ON CONFLICT DO NOTHING
                    RETURNING agent_id
                    """,
                    agent_dict,
                )

                # If we got here because of a name conflict,
                # we need to check if it's our own agent or somebody else's
                if cur.rowcount == 0:  # No insert happened because of a conflict
                    await cur.execute(
                        """
                        UPDATE v2.agent
                        SET
                          name = %(name)s,
                          description = %(description)s,
                          user_id = %(user_id)s::uuid,
                          runbook_structured = %(runbook_structured)s,
                          version = %(version)s,
                          updated_at = %(updated_at)s,
                          action_packages = %(action_packages)s,
                          mcp_servers = %(mcp_servers)s,
                          agent_architecture = %(agent_architecture)s,
                          question_groups = %(question_groups)s,
                          observability_configs = %(observability_configs)s,
                          platform_configs = %(platform_configs)s,
                          extra = %(extra)s,
                          mode = %(mode)s
                        WHERE
                          agent_id = %(agent_id)s::uuid
                          AND v2.check_user_access(user_id, %(user_id)s::uuid)
                          -- Make sure no name collision exists with other agents
                          AND (
                            -- Either name didn't change
                            name = %(name)s
                            -- Or no other agent has this name
                            OR NOT EXISTS (
                              SELECT 1 FROM v2.agent
                              WHERE LOWER(name) = LOWER(%(name)s)
                                AND user_id = %(user_id)s::uuid
                                AND agent_id != %(agent_id)s::uuid
                            )
                          )
                        RETURNING agent_id
                        """,
                        agent_dict,
                    )

                    # If we still didn't update anything, check if it's a name conflict
                    if cur.rowcount == 0:
                        # Check if it's a name conflict with another agent
                        await cur.execute(
                            """
                            SELECT 1 FROM v2.agent
                            WHERE LOWER(name) = LOWER(%(name)s)
                              AND user_id = %(user_id)s::uuid
                              AND agent_id != %(agent_id)s::uuid
                            """,
                            agent_dict,
                        )
                        if await cur.fetchone():
                            raise AgentWithNameAlreadyExistsError(
                                f"Agent name {agent.name!r} is not unique for user {user_id}"
                            )
                        else:
                            # Must be access denied or agent doesn't exist
                            await cur.execute(
                                "SELECT 1 FROM v2.agent WHERE agent_id = %(agent_id)s::uuid",
                                {"agent_id": agent.agent_id},
                            )
                            if not await cur.fetchone():
                                raise AgentNotFoundError(f"Agent {agent.agent_id} not found")
                            else:
                                raise UserAccessDeniedError(
                                    f"User {user_id} does not have access to agent {agent.agent_id}"
                                )
        except IntegrityError as e:
            # Catch the agent_id unique-index violation
            if "UNIQUE constraint failed: v2.agent.agent_id" in str(e):
                raise RecordAlreadyExistsError(
                    f"Agent {agent.agent_id} already exists",
                ) from e
            raise

    async def patch_agent(self, user_id: str, agent_id: str, name: str, description: str) -> None:
        """Update agent name and description."""
        try:
            async with self._cursor() as cur:
                await cur.execute(
                    """
                    UPDATE v2.agent
                    SET
                        name = %(name)s,
                        description = %(description)s
                    WHERE
                        agent_id = %(agent_id)s::uuid
                        AND v2.check_user_access(user_id, %(user_id)s::uuid)
                        -- Make sure no name collision exists with other agents
                        AND (
                        -- Either name didn't change
                        name = %(name)s
                        -- Or no other agent has this name
                        OR NOT EXISTS (
                            SELECT 1 FROM v2.agent
                            WHERE LOWER(name) = LOWER(%(name)s)
                            AND user_id = %(user_id)s::uuid
                            AND agent_id != %(agent_id)s::uuid
                        )
                        )
                    RETURNING agent_id
                    """,
                    {
                        "name": name,
                        "description": description,
                        "agent_id": agent_id,
                        "user_id": user_id,
                    },
                )
        except IntegrityError as e:
            if "UNIQUE constraint failed: v2.agent.name" in str(e):
                raise RecordAlreadyExistsError(
                    f"Agent name {name} already exists",
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
