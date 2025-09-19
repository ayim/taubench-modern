from psycopg.errors import IntegrityError
from psycopg.types.json import Jsonb
from structlog import get_logger

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

    logger = get_logger(__name__)

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

            # 4. Populate MCP servers and platform params, and return the agents
            agents = []
            for row in rows:
                agent = Agent.model_validate(row)
                agent = await self._populate_agent_mcp_servers(agent)
                agent = await self._populate_agent_platform_params(agent)
                agents.append(agent)
            return agents

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

            # 5. Return the agent with populated MCP servers and platform params
            agent = Agent.model_validate(row)
            agent = await self._populate_agent_mcp_servers(agent)
            return await self._populate_agent_platform_params(agent)

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

            # Return the agent with populated MCP servers and platform params
            agent = Agent.model_validate(row)
            agent = await self._populate_agent_mcp_servers(agent)
            return await self._populate_agent_platform_params(agent)

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
            "selected_tools",
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
                      observability_configs, platform_configs, extra, selected_tools, mode
                    )
                    VALUES (
                      %(agent_id)s::uuid, %(name)s, %(description)s,
                      %(user_id)s::uuid, %(runbook_structured)s, %(version)s,
                      %(created_at)s, %(updated_at)s, %(action_packages)s,
                      %(mcp_servers)s, %(agent_architecture)s, %(question_groups)s,
                      %(observability_configs)s, %(platform_configs)s,
                      %(extra)s, %(selected_tools)s, %(mode)s
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
                          selected_tools = %(selected_tools)s,
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

        # Handle MCP server associations if the agent has mcp_server_ids
        if hasattr(agent, "mcp_server_ids") and agent.mcp_server_ids:
            await self.associate_mcp_servers_with_agent(agent.agent_id, agent.mcp_server_ids)

        # Handle platform params associations if the agent has platform_params_ids
        if hasattr(agent, "platform_params_ids") and agent.platform_params_ids:
            await self.associate_platform_params_with_agent(
                agent.agent_id, agent.platform_params_ids
            )

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

    async def _populate_agent_mcp_servers(self, agent: Agent) -> Agent:
        """Populate MCP servers for an agent using both join table and JSON column."""
        # 1. Fetch global MCP server IDs from the join table
        mcp_server_ids = await self.get_agent_mcp_server_ids(agent.agent_id)

        # 2. Parse agent-specific/resolved MCP servers from the JSON column
        resolved_mcp_servers = []
        if hasattr(agent, "mcp_servers") and agent.mcp_servers:
            import json

            from agent_platform.core.mcp.mcp_server import MCPServer

            try:
                # If mcp_servers is already a list of MCPServer objects, use them
                if isinstance(agent.mcp_servers, list) and all(
                    isinstance(s, MCPServer) for s in agent.mcp_servers
                ):
                    resolved_mcp_servers = agent.mcp_servers
                else:
                    # Parse the JSON and create MCPServer objects
                    mcp_servers_data = agent.mcp_servers
                    if isinstance(mcp_servers_data, str):
                        mcp_servers_data = json.loads(mcp_servers_data)

                    for server_data in mcp_servers_data:
                        if isinstance(server_data, dict):
                            resolved_mcp_servers.append(MCPServer.model_validate(server_data))
            except Exception as e:
                # Log error but continue
                import structlog

                logger = structlog.get_logger(__name__)
                logger.warning(
                    f"Failed to parse resolved MCP servers from JSON for agent "
                    f"{agent.agent_id}: {e}"
                )

        # Return agent with:
        # - mcp_server_ids: Global MCP server IDs from join table
        # - mcp_servers: Agent-specific/resolved MCP server configs from JSON column
        return agent.copy(mcp_servers=resolved_mcp_servers, mcp_server_ids=mcp_server_ids)

    async def _populate_agent_platform_params(self, agent: Agent) -> Agent:
        """
        Populate platform params IDs and resolved platform configs for an agent from the join table.
        """
        # Fetch platform params IDs from the join table
        platform_params_ids = await self.get_agent_platform_params_ids(agent.agent_id)

        # Resolve platform configs from the IDs
        resolved_platform_configs = []
        if platform_params_ids:
            for platform_id in platform_params_ids:
                try:
                    platform_params = await self.get_platform_params(platform_id)
                    resolved_platform_configs.append(platform_params)
                    self.logger.info(
                        f"Resolved platform params ID {platform_id} to {platform_params.kind}"
                    )
                except Exception as e:
                    self.logger.warning(f"Failed to resolve platform params ID {platform_id}: {e}")

        # Combine existing platform_configs with resolved ones
        all_platform_configs = list(agent.platform_configs) + resolved_platform_configs

        # Return agent with both platform_params_ids and resolved platform_configs populated
        return agent.copy(
            platform_params_ids=platform_params_ids, platform_configs=all_platform_configs
        )

    async def count_agents_by_mode(self, mode: str) -> int:
        """Count the number of agents by mode."""
        async with self._cursor() as cur:
            # 1. Get the count
            await cur.execute("SELECT COUNT(*) FROM v2.agent WHERE mode = %(mode)s", {"mode": mode})

            # 2. No results?
            if not (row := await cur.fetchone()):
                return 0

            # 3. Return the count
            return row["count"]

    async def associate_platform_params_with_agent(
        self, agent_id: str, platform_params_ids: list[str]
    ) -> None:
        """Associate platform params with an agent, replacing any existing associations.

        PostgreSQL-specific implementation that handles UUID validation and casting.
        """
        self._validate_uuid(agent_id)

        async with self._cursor() as cur:
            # First, remove existing associations
            await cur.execute(
                """DELETE FROM v2.agent_platform_params
                   WHERE agent_id = %(agent_id)s::uuid""",
                {"agent_id": agent_id},
            )

            # Then add new associations
            if platform_params_ids:
                for platform_params_id in platform_params_ids:
                    await cur.execute(
                        """INSERT INTO v2.agent_platform_params (agent_id, platform_params_id)
                           VALUES (%(agent_id)s::uuid, %(platform_params_id)s::uuid)""",
                        {"agent_id": agent_id, "platform_params_id": platform_params_id},
                    )
