import uuid
from datetime import UTC, datetime

from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from agent_platform.core.mcp.mcp_server import MCPServer, MCPServerSource
from agent_platform.server.storage.errors import (
    MCPServerNotFoundError,
    MCPServerWithNameAlreadyExistsError,
    RecordAlreadyExistsError,
)
from agent_platform.server.storage.postgres.common import CommonMixin


class PostgresStorageMCPServersMixin(CommonMixin):
    """Mixin for PostgreSQL MCP server operations."""

    async def create_mcp_server(self, mcp_server: MCPServer, source: MCPServerSource) -> None:
        """Create a new MCP server."""
        # 1. Generate ID and timestamps
        mcp_server_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        # 2. Prepare the config as JSONB
        config = Jsonb(mcp_server.model_dump())

        # 3. Insert the MCP server
        try:
            async with self._cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO v2.mcp_server (
                        mcp_server_id, name, config, source, created_at, updated_at
                    )
                    VALUES (
                        %s::uuid, %s, %s, %s, %s, %s
                    )
                    """,
                    (mcp_server_id, mcp_server.name, config, source.value, now, now),
                )
        except UniqueViolation as e:
            if "mcp_server_pkey" in str(e):
                raise RecordAlreadyExistsError(
                    f"MCP server {mcp_server_id} already exists",
                ) from e
            elif "idx_mcp_server_name" in str(e):
                raise MCPServerWithNameAlreadyExistsError(
                    f"MCP server with name '{mcp_server.name}' already exists",
                ) from e
            raise

    async def get_mcp_server(self, mcp_server_id: str) -> MCPServer:
        """Get an MCP server by ID."""
        # 1. Validate the uuid
        self._validate_uuid(mcp_server_id)

        async with self._cursor() as cur:
            # 2. Get the MCP server
            await cur.execute(
                """
                SELECT config FROM v2.mcp_server
                WHERE mcp_server_id = %s::uuid
                """,
                (mcp_server_id,),
            )

            # 3. No MCP server found?
            if not (row := await cur.fetchone()):
                raise MCPServerNotFoundError(f"MCP server {mcp_server_id} not found")

            # 4. Return the MCP server from config
            return MCPServer.model_validate(row["config"])

    async def list_mcp_servers(self) -> dict[str, MCPServer]:
        """List all MCP servers."""

        async with self._cursor() as cur:
            # 2. Get all MCP servers for this user
            await cur.execute(
                """
                SELECT mcp_server_id, config FROM v2.mcp_server
                ORDER BY created_at DESC
                """,
            )

            # 3. No MCP servers found?
            if not (rows := await cur.fetchall()):
                return {}

            # 4. Return the MCP servers as a dict of id -> MCPServer
            return {
                str(row["mcp_server_id"]): MCPServer.model_validate(row["config"]) for row in rows
            }

    async def update_mcp_server(
        self,
        mcp_server_id: str,
        mcp_server: MCPServer,
        mcp_server_source: MCPServerSource,
    ) -> None:
        """Update an MCP server."""
        # 1. Validate the uuid
        self._validate_uuid(mcp_server_id)

        # 2. Prepare the config as JSONB
        config = Jsonb(mcp_server.model_dump())
        now = datetime.now(UTC)

        # 3. Update the MCP server
        try:
            async with self._cursor() as cur:
                await cur.execute(
                    """
                    UPDATE v2.mcp_server
                    SET
                        name = %s,
                        config = %s,
                        source = %s,
                        updated_at = %s
                    WHERE mcp_server_id = %s::uuid
                    RETURNING mcp_server_id
                    """,
                    (mcp_server.name, config, mcp_server_source.value, now, mcp_server_id),
                )

                # 4. Check if update succeeded
                if not await cur.fetchone():
                    raise MCPServerNotFoundError(f"MCP server {mcp_server_id} not found")
        except UniqueViolation as e:
            if "idx_mcp_server_name" in str(e):
                raise MCPServerWithNameAlreadyExistsError(
                    f"MCP server with name '{mcp_server.name}' already exists",
                ) from e
            raise

    async def delete_mcp_server(self, mcp_server_id: str) -> None:
        """Delete an MCP server."""
        # 1. Validate the uuid
        self._validate_uuid(mcp_server_id)

        async with self._cursor() as cur:
            # 2. Delete the MCP server
            await cur.execute(
                """
                DELETE FROM v2.mcp_server
                WHERE mcp_server_id = %s::uuid
                RETURNING mcp_server_id
                """,
                (mcp_server_id,),
            )

            # 3. Check if delete succeeded
            if not await cur.fetchone():
                raise MCPServerNotFoundError(f"MCP server {mcp_server_id} not found")
