from structlog import get_logger

from agent_platform.core.mcp.mcp_server import MCPServer, MCPServerSource
from agent_platform.server.storage.common import CommonMixin
from agent_platform.server.storage.errors import ConfigDecryptionError, MCPServerNotFoundError
from agent_platform.server.storage.sqlite.cursor import CursorMixin


class SQLiteStorageMCPServersMixin(CursorMixin, CommonMixin):
    """
    Mixin providing SQLite-based MCP server operations.
    """

    _logger = get_logger(__name__)

    # -------------------------------------------------------------------------
    # MCP Servers
    # -------------------------------------------------------------------------

    async def list_mcp_servers(self) -> dict[str, MCPServer]:
        """List all MCP servers."""

        async with self._cursor() as cur:
            # 2. Get all MCP servers
            await cur.execute(
                """
                SELECT mcp_server_id, enc_config FROM v2_mcp_server
                ORDER BY created_at DESC
                """,
            )

            # 3. No MCP servers found?
            if not (rows := await cur.fetchall()):
                return {}

            # 4. Decrypt and return the MCP servers as a dict of id -> MCPServer
            result = {}
            for row in rows:
                server_id = row[0]
                encrypted_config = row[1]
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
                SELECT mcp_server_id, enc_config, source FROM v2_mcp_server
                WHERE name = ? AND source = ?
                """,
                (name, source.value),
            )

            # 3. No MCP server found?
            if not (row := await cur.fetchone()):
                return None

            # 4. Decrypt and return the MCP server ID, config, and source
            encrypted_config = row[1]
            try:
                config_dict = self._decrypt_config(encrypted_config)
                mcp_server = MCPServer.model_validate(config_dict)
                return row[0], mcp_server, MCPServerSource(row[2])
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
                SELECT mcp_server_id, name FROM v2_mcp_server
                WHERE source = ?
                ORDER BY created_at DESC
                """,
                (source.value,),
            )

            # 3. No MCP servers found?
            if not (rows := await cur.fetchall()):
                return {}

            # 4. Return the MCP servers as a dict of name -> id
            return {row[1]: row[0] for row in rows}

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
            # 2. First, get the deployment IDs before deleting
            # (SQLite doesn't support RETURNING in DELETE)
            placeholders = ",".join("?" * len(mcp_server_ids))
            await cur.execute(
                f"""
                SELECT mcp_server_id, mcp_runtime_deployment_id FROM v2_mcp_server
                WHERE mcp_server_id IN ({placeholders})
                """,
                mcp_server_ids,
            )

            rows = list(await cur.fetchall())
            if len(rows) != len(mcp_server_ids):
                found_ids = {row["mcp_server_id"] for row in rows}
                missing_ids = set(mcp_server_ids) - found_ids
                raise MCPServerNotFoundError(f"MCP servers not found: {', '.join(missing_ids)}")

            # 3. Extract deployment IDs from deleted servers
            deleted_servers = [(row["mcp_server_id"], row["mcp_runtime_deployment_id"]) for row in rows]

            # 4. Delete the MCP servers
            await cur.execute(
                f"""
                DELETE FROM v2_mcp_server
                WHERE mcp_server_id IN ({placeholders})
                """,
                mcp_server_ids,
            )

            return deleted_servers

    async def count_mcp_servers(self) -> int:
        """Count the number of MCP servers."""
        async with self._cursor() as cur:
            await cur.execute("SELECT COUNT(*) AS cnt FROM v2_mcp_server")
            row = await cur.fetchone()
        return row["cnt"] if row else 0
