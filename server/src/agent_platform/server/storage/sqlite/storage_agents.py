import json

import aiosqlite
from structlog import get_logger

from agent_platform.core.agent import Agent
from agent_platform.server.storage.common import CommonMixin
from agent_platform.server.storage.errors import (
    AgentNotFoundError,
    AgentWithNameAlreadyExistsError,
    ReferenceIntegrityError,
    StorageError,
    UserAccessDeniedError,
)
from agent_platform.server.storage.sqlite.cursor import CursorMixin


class SQLiteStorageAgentsMixin(CursorMixin, CommonMixin):
    """
    Mixin providing SQLite-based agent operations.
    """

    _logger = get_logger(__name__)

    # -------------------------------------------------------------------------
    # Agents
    # -------------------------------------------------------------------------

    async def list_agents(self, user_id: str) -> list[Agent]:
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

        agents = []
        for row in rows:
            agent = Agent.model_validate(self._convert_agent_json_fields(dict(row)))
            agent = await self._populate_agent_mcp_servers(agent)
            agents.append(agent)

        return agents

    async def get_agent(self, user_id: str, agent_id: str) -> Agent:
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
            raise UserAccessDeniedError(
                f"User {user_id} does not have access to agent {agent_id}",
            )

        # Convert JSON columns and return
        row_dict = dict(row)
        row_dict.pop("has_access", None)
        agent = Agent.model_validate(self._convert_agent_json_fields(row_dict))

        # Populate MCP servers from join table
        return await self._populate_agent_mcp_servers(agent)

    async def get_agent_by_name(self, user_id: str, name: str) -> Agent:
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
            raise UserAccessDeniedError(
                f"User {user_id} does not have access to agent {name}",
            )

        row_dict = dict(row)
        row_dict.pop("has_access", None)
        agent = Agent.model_validate(self._convert_agent_json_fields(row_dict))

        # Populate MCP servers from join table
        return await self._populate_agent_mcp_servers(agent)

    async def upsert_agent(self, user_id: str, agent: Agent) -> None:  # noqa: C901, PLR0912
        """Create or update an agent, avoiding false-positives on
        the name-uniqueness index."""
        self._validate_uuid(user_id)
        self._validate_uuid(agent.agent_id)

        # Convert the agent to a dict; JSON-ify the complex fields
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
            agent_dict[field] = json.dumps(agent_dict.get(field))

        try:
            async with self._cursor() as cur:
                # First attempt an INSERT with DO NOTHING to avoid errors
                await cur.execute(
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
                    agent_dict,
                )

                # If we got here because of a conflict, try to update
                if cur.rowcount == 0:  # No insert happened
                    await cur.execute(
                        """
                        UPDATE v2_agent
                        SET
                            name = :name,
                            description = :description,
                            runbook_structured = :runbook_structured,
                            version = :version,
                            updated_at = :updated_at,
                            action_packages = :action_packages,
                            mcp_servers = :mcp_servers,
                            agent_architecture = :agent_architecture,
                            question_groups = :question_groups,
                            observability_configs = :observability_configs,
                            platform_configs = :platform_configs,
                            extra = :extra,
                            mode = :mode
                        WHERE
                            agent_id = :agent_id
                            AND v2_check_user_access(user_id, :user_id) = 1
                            -- Make sure no name collision exists with other agents
                            AND (
                                -- Either name didn't change
                                LOWER(name) = LOWER(:name)
                                -- Or no other agent has this name
                                OR NOT EXISTS (
                                    SELECT 1 FROM v2_agent
                                    WHERE LOWER(name) = LOWER(:name)
                                      AND user_id = :user_id
                                      AND agent_id != :agent_id
                                )
                            )
                        """,
                        agent_dict,
                    )

                    # If we still didn't update anything, determine why
                    if cur.rowcount == 0:
                        # Check if agent exists
                        await cur.execute(
                            "SELECT 1 FROM v2_agent WHERE agent_id = :agent_id",
                            {"agent_id": agent.agent_id},
                        )

                        if not await cur.fetchone():
                            # The agent doesn't exist - check if it was a name conflict
                            await cur.execute(
                                """
                                SELECT 1 FROM v2_agent
                                WHERE LOWER(name) = LOWER(:name) AND user_id = :user_id
                                """,
                                {"name": agent.name, "user_id": user_id},
                            )
                            if await cur.fetchone():
                                raise AgentWithNameAlreadyExistsError(
                                    f"Agent name '{agent.name}' is not unique for user {user_id}"
                                )
                            else:
                                # This shouldn't happen - could be a race condition
                                raise StorageError(
                                    f"Upsert failed unexpectedly for agent {agent.agent_id}"
                                )
                        else:
                            # Agent exists, check user access
                            await cur.execute(
                                """
                                SELECT
                                  v2_check_user_access(user_id, :user_id) as has_access
                                FROM v2_agent WHERE agent_id = :agent_id
                                """,
                                {"agent_id": agent.agent_id, "user_id": user_id},
                            )
                            row = await cur.fetchone()
                            if not row or not row["has_access"]:
                                raise UserAccessDeniedError(
                                    f"User {user_id} does not have permission "
                                    f"to update agent {agent.agent_id}"
                                )

                            # Must be a name collision with another agent
                            await cur.execute(
                                """
                                SELECT 1 FROM v2_agent
                                WHERE LOWER(name) = LOWER(:name)
                                    AND user_id = :user_id
                                    AND agent_id != :agent_id
                                """,
                                {
                                    "name": agent.name,
                                    "user_id": user_id,
                                    "agent_id": agent.agent_id,
                                },
                            )
                            if await cur.fetchone():
                                raise AgentWithNameAlreadyExistsError(
                                    f"Agent name '{agent.name}' is not unique for user {user_id}"
                                )
                            else:
                                # Shouldn't happen - defensive coding
                                raise StorageError(
                                    f"Upsert failed unexpectedly for agent {agent.agent_id}"
                                )

        except aiosqlite.IntegrityError as e:
            # We should rarely hit this with our logic, but handle race conditions
            if "UNIQUE constraint failed" in str(e) and (
                "idx_agent_name_per_user_v2" in str(e) or ".name" in str(e)
            ):
                raise AgentWithNameAlreadyExistsError(
                    f"Agent name {agent.name} is not unique for user {user_id}"
                ) from e
            elif "foreign key constraint" in str(e).lower():
                raise ReferenceIntegrityError(
                    "Invalid foreign key reference updating/inserting agent"
                ) from e
            else:
                self._logger.error("Unexpected database integrity error", error=str(e))
                raise StorageError(f"Database integrity error: {e}") from e
        except (
            UserAccessDeniedError,
            AgentWithNameAlreadyExistsError,
            AgentNotFoundError,
            ReferenceIntegrityError,
        ) as e:
            # Re-raise specific errors
            raise e
        except Exception as e:
            self._logger.error(
                "Unexpected error during agent upsert",
                error=str(e),
                exc_info=e,
            )
            raise StorageError(f"An unexpected error occurred: {e}") from e

        # Handle MCP server associations if the agent has mcp_server_ids
        if hasattr(agent, "mcp_server_ids") and agent.mcp_server_ids:
            await self.associate_mcp_servers_with_agent(agent.agent_id, agent.mcp_server_ids)

    async def patch_agent(self, user_id: str, agent_id: str, name: str, description: str) -> None:
        """Update agent name and description."""
        try:
            async with self._cursor() as cur:
                await cur.execute(
                    """
                    UPDATE v2_agent
                    SET
                        name = :name,
                        description = :description
                    WHERE
                        agent_id = :agent_id
                        AND v2_check_user_access(user_id, :user_id) = 1
                        -- Make sure no name collision exists with other agents
                        AND (
                            -- Either name didn't change
                            LOWER(name) = LOWER(:name)
                            -- Or no other agent has this name
                            OR NOT EXISTS (
                                SELECT 1 FROM v2_agent
                                WHERE LOWER(name) = LOWER(:name)
                                    AND user_id = :user_id
                                    AND agent_id != :agent_id
                            )
                        )
                    """,
                    {
                        "name": name,
                        "description": description,
                        "agent_id": agent_id,
                        "user_id": user_id,
                    },
                )
        except aiosqlite.IntegrityError as e:
            if "UNIQUE constraint failed" in str(e) and (
                "idx_agent_name_per_user_v2" in str(e) or ".name" in str(e)
            ):
                raise AgentWithNameAlreadyExistsError(
                    f"Agent name {name} is not unique for user {user_id}"
                ) from e
            elif "foreign key constraint" in str(e).lower():
                raise ReferenceIntegrityError(
                    "Invalid foreign key reference updating/inserting agent"
                ) from e
            else:
                self._logger.error("Unexpected database integrity error", error=str(e))
                raise StorageError(f"Database integrity error: {e}") from e
        except Exception as e:
            self._logger.error(
                "Unexpected error during agent upsert",
                error=str(e),
                exc_info=e,
            )
            raise StorageError(f"An unexpected error occurred: {e}") from e

    async def delete_agent(self, user_id: str, agent_id: str) -> None:
        """Delete an agent, enforcing user access."""
        self._validate_uuid(user_id)
        self._validate_uuid(agent_id)

        # First check if agent exists
        agent_exists = await self._agent_exists(agent_id)
        if not agent_exists:
            raise AgentNotFoundError(f"Agent {agent_id} not found")

        # Then check user access
        if not await self._user_can_access_agent(user_id, agent_id):
            raise UserAccessDeniedError(
                f"User {user_id} does not have access to agent {agent_id}",
            )

        async with self._cursor() as cur:
            await cur.execute(
                """
                DELETE FROM v2_agent
                WHERE agent_id = :agent_id
                """,
                {"agent_id": agent_id},
            )

    async def count_agents(self) -> int:
        """Count the number of agents."""
        async with self._cursor() as cur:
            await cur.execute("SELECT COUNT(*) AS cnt FROM v2_agent")
            row = await cur.fetchone()
        return row["cnt"] if row else 0

    async def count_agents_by_mode(self, mode: str) -> int:
        """Count the number of agents by mode."""
        async with self._cursor() as cur:
            await cur.execute(
                "SELECT COUNT(*) AS cnt FROM v2_agent WHERE mode = :mode", {"mode": mode}
            )
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
        """Convert JSON string fields in agent dict to
        Python objects (similar to Postgres mixin)."""
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
            if agent_dict.get(field) is not None:
                agent_dict[field] = json.loads(agent_dict[field])
            else:
                agent_dict[field] = {}
        return agent_dict

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
