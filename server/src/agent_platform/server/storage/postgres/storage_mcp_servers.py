from psycopg.sql import SQL
from structlog import get_logger

from agent_platform.core.mcp.mcp_server import MCPServer, MCPServerSource
from agent_platform.server.storage.common import CommonMixin
from agent_platform.server.storage.errors import (
    ConfigDecryptionError,
    MCPServerNotFoundError,
)
from agent_platform.server.storage.postgres.cursor import CursorMixin


class PostgresStorageMCPServersMixin(CursorMixin, CommonMixin):
    """Mixin for PostgreSQL MCP server operations."""

    _logger = get_logger(__name__)

    async def list_mcp_servers(self) -> dict[str, MCPServer]:
        """List all MCP servers."""

        async with self._cursor() as cur:
            # 2. Get all MCP servers
            await cur.execute(
                """
                SELECT mcp_server_id, enc_config::text AS enc_config FROM v2.mcp_server
                ORDER BY created_at DESC
                """,
            )

            # 3. No MCP servers found?
            if not (rows := await cur.fetchall()):
                return {}

            # 4. Decrypt and return the MCP servers as a dict of id -> MCPServer
            result = {}
            for row in rows:
                server_id = str(row["mcp_server_id"])
                encrypted_config = row["enc_config"]
                try:
                    config_dict = self._decrypt_config(encrypted_config)
                    result[server_id] = MCPServer.model_validate(config_dict)
                except Exception as e:
                    # Skip corrupted entries but log for monitoring
                    self._logger.warning(f"Skipping MCP server {server_id} due to decryption failure: {e}")
                    continue
            return result

    async def get_mcp_server_by_name(
        self, name: str, source: MCPServerSource
    ) -> tuple[str, MCPServer, MCPServerSource] | None:
        """Get an MCP server by name"""
        async with self._cursor() as cur:
            # 2. Get the MCP server by name and source
            await cur.execute(
                """
                SELECT mcp_server_id, enc_config::text AS enc_config, source FROM v2.mcp_server
                WHERE name = %s AND source = %s
                """,
                (name, source.value),
            )

            # 3. No MCP server found?
            if not (row := await cur.fetchone()):
                return None

            # 4. Decrypt and return the MCP server ID, config, and source
            encrypted_config = row["enc_config"]
            try:
                config_dict = self._decrypt_config(encrypted_config)
                mcp_server = MCPServer.model_validate(config_dict)
                return (
                    str(row["mcp_server_id"]),
                    mcp_server,
                    MCPServerSource(row["source"]),
                )
            except Exception as e:
                raise ConfigDecryptionError(
                    f"Failed to decrypt MCP server configuration for '{name}' with source '{source.value}'"
                ) from e

    async def list_mcp_servers_by_source(self, source: MCPServerSource) -> dict[str, str]:
        """List MCP servers by source"""
        async with self._cursor() as cur:
            # 2. Get all MCP servers by source
            await cur.execute(
                """
                SELECT mcp_server_id, name FROM v2.mcp_server
                WHERE source = %s
                ORDER BY created_at DESC
                """,
                (source.value,),
            )

            # 3. No MCP servers found?
            if not (rows := await cur.fetchall()):
                return {}

            # 4. Return the MCP servers as a dict of name -> id
            return {row["name"]: str(row["mcp_server_id"]) for row in rows}

    async def delete_mcp_server(self, mcp_server_ids: list[str]) -> list[tuple[str, str | None]]:
        """
        Delete one or more MCP servers.

        Returns list of (mcp_server_id, mcp_runtime_deployment_id) tuples.
        """
        # 1. Validate all uuids
        for server_id in mcp_server_ids:
            self._validate_uuid(server_id)

        if not mcp_server_ids:
            return []

        async with self._transaction() as cur:
            # 2. Delete the MCP servers and return their deployment IDs
            placeholders = SQL(",").join([SQL("%s::uuid")] * len(mcp_server_ids))
            query = SQL("""
                DELETE FROM v2.mcp_server
                WHERE mcp_server_id IN ({placeholders})
                RETURNING mcp_server_id, mcp_runtime_deployment_id
                """).format(placeholders=placeholders)
            await cur.execute(query, mcp_server_ids)

            # 3. Check if all deletes succeeded
            rows = await cur.fetchall()
            deleted_ids = [str(row["mcp_server_id"]) for row in rows]
            missing_ids = set(mcp_server_ids) - set(deleted_ids)
            if missing_ids:
                raise MCPServerNotFoundError(f"MCP servers not found: {', '.join(missing_ids)}")

            # 4. Extract deployment IDs from deleted servers
            deleted_servers = [(str(row["mcp_server_id"]), row["mcp_runtime_deployment_id"]) for row in rows]

            return deleted_servers

    async def count_mcp_servers(self) -> int:
        """Count the number of MCP servers."""
        async with self._cursor() as cur:
            await cur.execute("SELECT COUNT(*) AS cnt FROM v2.mcp_server")
            if not (row := await cur.fetchone()):
                return 0

            return row["cnt"]
