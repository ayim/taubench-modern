import json
import uuid
from datetime import UTC, datetime
from sqlite3 import IntegrityError

from structlog import get_logger

from agent_platform.core.mcp.mcp_server import MCPServer, MCPServerSource
from agent_platform.server.storage.errors import (
    MCPServerNotFoundError,
    MCPServerWithNameAlreadyExistsError,
    RecordAlreadyExistsError,
)
from agent_platform.server.storage.sqlite.common import CommonMixin


class SQLiteStorageMCPServersMixin(CommonMixin):
    """
    Mixin providing SQLite-based MCP server operations.
    """

    _logger = get_logger(__name__)

    def _encrypt_config(self, config_dict: dict) -> str:
        """Encrypt the MCP server config dictionary using the secret manager."""
        config_json = json.dumps(config_dict, sort_keys=True)
        return self._secret_manager.store(config_json)

    def _decrypt_config(self, encrypted_config: str) -> dict:
        """Decrypt the MCP server config using the secret manager and return as dictionary."""
        decrypted_json = self._secret_manager.fetch(encrypted_config)
        return json.loads(decrypted_json)

    # -------------------------------------------------------------------------
    # MCP Servers
    # -------------------------------------------------------------------------
    async def create_mcp_server(self, mcp_server: MCPServer, source: MCPServerSource) -> None:
        """Create a new MCP server."""
        # 1. Generate ID and timestamps
        mcp_server_id = str(uuid.uuid4())
        now = datetime.now(UTC).isoformat()

        # 2. Prepare the config as encrypted JSON
        config_dict = mcp_server.model_dump()
        encrypted_config = self._encrypt_config(config_dict)

        # 3. Insert the MCP server
        # The 'source' field is used to track where the MCP server entry originated from.
        # This is important for syncing the MCP servers list from a file, such as when
        # adding or removing MCP servers to match the list defined in a configuration file.
        try:
            async with self._cursor() as cur:
                await cur.execute(
                    """
                INSERT INTO v2_mcp_server (
                    mcp_server_id, name, enc_config, source, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (mcp_server_id, mcp_server.name, encrypted_config, source.value, now, now),
                )
        except IntegrityError as e:
            error_msg = str(e).lower()
            if "unique constraint failed: v2_mcp_server.mcp_server_id" in error_msg:
                raise RecordAlreadyExistsError(
                    f"MCP server {mcp_server_id} already exists",
                ) from e
            elif "unique constraint failed: v2_mcp_server.name" in error_msg:
                raise MCPServerWithNameAlreadyExistsError(
                    f"MCP server with name '{mcp_server.name}' already exists",
                ) from e
            raise

    async def get_mcp_server(self, mcp_server_id: str) -> MCPServer:
        """Get an MCP server by ID."""
        # 1. Validate the uuid
        self._validate_uuid(mcp_server_id)

        # TODO: Implement a sync method to add or remove MCP servers from the list
        # before get_mcp_server is called, ensuring the database matches the source list.

        async with self._cursor() as cur:
            # 2. Get the MCP server
            await cur.execute(
                """
                SELECT enc_config FROM v2_mcp_server
                WHERE mcp_server_id = ?
                """,
                (mcp_server_id,),
            )

            # 3. No MCP server found?
            if not (row := await cur.fetchone()):
                raise MCPServerNotFoundError(f"MCP server {mcp_server_id} not found")

            # 4. Decrypt and return the MCP server from enc_config
            encrypted_config = row[0]
            config_dict = self._decrypt_config(encrypted_config)
            return MCPServer.model_validate(config_dict)

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
                config_dict = self._decrypt_config(encrypted_config)
                result[server_id] = MCPServer.model_validate(config_dict)
            return result

    async def update_mcp_server(
        self,
        mcp_server_id: str,
        mcp_server: MCPServer,
        mcp_server_source: MCPServerSource,
    ) -> None:
        """Update an MCP server."""
        # 1. Validate the uuid
        self._validate_uuid(mcp_server_id)

        # 2. Prepare the config as encrypted JSON
        config_dict = mcp_server.model_dump()
        encrypted_config = self._encrypt_config(config_dict)
        now = datetime.now(UTC).isoformat()

        # 3. Update the MCP server
        try:
            async with self._cursor() as cur:
                await cur.execute(
                    """
                    UPDATE v2_mcp_server
                    SET
                        name = ?,
                        enc_config = ?,
                        source = ?,
                        updated_at = ?
                    WHERE mcp_server_id = ?
                    """,
                    (
                        mcp_server.name,
                        encrypted_config,
                        mcp_server_source.value,
                        now,
                        mcp_server_id,
                    ),
                )

                # 4. Check if update succeeded
                if cur.rowcount == 0:
                    raise MCPServerNotFoundError(f"MCP server {mcp_server_id} not found")
        except IntegrityError as e:
            error_msg = str(e).lower()
            if "unique constraint failed: v2_mcp_server.name" in error_msg:
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
                DELETE FROM v2_mcp_server
                WHERE mcp_server_id = ?
                """,
                (mcp_server_id,),
            )

            # 3. Check if delete succeeded
            if cur.rowcount == 0:
                raise MCPServerNotFoundError(f"MCP server {mcp_server_id} not found")
