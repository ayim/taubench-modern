import uuid
from datetime import UTC, datetime
from sqlite3 import IntegrityError

from structlog import get_logger

from agent_platform.core.mcp.mcp_server import MCPServer, MCPServerSource
from agent_platform.server.storage.common import CommonMixin
from agent_platform.server.storage.errors import (
    ConfigDecryptionError,
    MCPServerNotFoundError,
    MCPServerWithNameAlreadyExistsError,
    RecordAlreadyExistsError,
)
from agent_platform.server.storage.sqlite.cursor import CursorMixin


class SQLiteStorageMCPServersMixin(CursorMixin, CommonMixin):
    """
    Mixin providing SQLite-based MCP server operations.
    """

    _logger = get_logger(__name__)

    # -------------------------------------------------------------------------
    # MCP Servers
    # -------------------------------------------------------------------------
    async def create_mcp_server(
        self,
        mcp_server: MCPServer,
        source: MCPServerSource,
        mcp_runtime_deployment_id: str | None = None,
    ) -> str:
        """Create a new MCP server. Returns the generated MCP server ID."""
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
            async with self._transaction() as cur:
                await cur.execute(
                    """
                INSERT INTO v2_mcp_server (
                    mcp_server_id, name, enc_config, source, mcp_runtime_deployment_id,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        mcp_server_id,
                        mcp_server.name,
                        encrypted_config,
                        source.value,
                        mcp_runtime_deployment_id,
                        now,
                        now,
                    ),
                )
        except IntegrityError as e:
            error_msg = str(e).lower()
            if "unique constraint failed: v2_mcp_server.mcp_server_id" in error_msg:
                raise RecordAlreadyExistsError(
                    f"MCP server {mcp_server_id} already exists",
                ) from e
            elif "unique constraint failed: v2_mcp_server.name, v2_mcp_server.source" in error_msg:
                raise MCPServerWithNameAlreadyExistsError(
                    f"MCP server with name '{mcp_server.name}' and source "
                    f"'{source.value}' already exists",
                ) from e
            raise

        return mcp_server_id

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
            try:
                config_dict = self._decrypt_config(encrypted_config)
                return MCPServer.model_validate(config_dict)
            except Exception as e:
                raise ConfigDecryptionError(
                    f"Failed to decrypt MCP server configuration for {mcp_server_id}"
                ) from e

    async def get_mcp_server_with_metadata(
        self, mcp_server_id: str
    ) -> tuple[MCPServer, MCPServerSource]:
        """Get an MCP server by ID with its source information."""
        # 1. Validate the uuid
        self._validate_uuid(mcp_server_id)

        async with self._cursor() as cur:
            # 2. Get the MCP server with source
            await cur.execute(
                """
                SELECT enc_config, source FROM v2_mcp_server
                WHERE mcp_server_id = ?
                """,
                (mcp_server_id,),
            )

            # 3. No MCP server found?
            if not (row := await cur.fetchone()):
                raise MCPServerNotFoundError(f"MCP server {mcp_server_id} not found")

            # 4. Decrypt and return the MCP server and source
            encrypted_config = row[0]
            try:
                config_dict = self._decrypt_config(encrypted_config)
                mcp_server = MCPServer.model_validate(config_dict)
                source = MCPServerSource(row[1])
                return mcp_server, source
            except Exception as e:
                raise ConfigDecryptionError(
                    f"Failed to decrypt MCP server configuration for {mcp_server_id}"
                ) from e

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
                    self._logger.warning(
                        f"Skipping MCP server {server_id} due to decryption failure: {e}"
                    )
                    continue
            return result

    async def list_mcp_servers_with_metadata(self) -> dict[str, tuple[MCPServer, MCPServerSource]]:
        """List all MCP servers with their source information."""

        async with self._cursor() as cur:
            # 2. Get all MCP servers with source information
            await cur.execute(
                """
                SELECT mcp_server_id, enc_config, source FROM v2_mcp_server
                ORDER BY created_at DESC
                """,
            )

            # 3. No MCP servers found?
            if not (rows := await cur.fetchall()):
                return {}

            # 4. Decrypt and return the MCP servers as a dict of id -> (MCPServer, MCPServerSource)
            result = {}
            for row in rows:
                server_id = row[0]
                encrypted_config = row[1]
                try:
                    config_dict = self._decrypt_config(encrypted_config)
                    mcp_server = MCPServer.model_validate(config_dict)
                    source = MCPServerSource(row[2])
                    result[server_id] = (mcp_server, source)
                except Exception as e:
                    # Skip corrupted entries but log for monitoring
                    self._logger.warning(
                        f"Skipping MCP server {server_id} due to decryption failure: {e}"
                    )
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
                    f"Failed to decrypt MCP server configuration for '{name}' with source "
                    f"'{source.value}'"
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

    async def get_mcp_servers_by_ids(self, mcp_server_ids: list[str]) -> dict[str, MCPServer]:
        """Get multiple MCP servers by their IDs."""
        if not mcp_server_ids:
            return {}

        # Validate all UUIDs
        for mcp_server_id in mcp_server_ids:
            self._validate_uuid(mcp_server_id)

        # Create placeholders for the IN clause
        placeholders = ",".join("?" * len(mcp_server_ids))

        async with self._cursor() as cur:
            await cur.execute(
                f"""
                SELECT mcp_server_id, enc_config FROM v2_mcp_server
                WHERE mcp_server_id IN ({placeholders})
                """,
                mcp_server_ids,
            )

            rows = await cur.fetchall()
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
            async with self._transaction() as cur:
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
            if "unique constraint failed: v2_mcp_server.name, v2_mcp_server.source" in error_msg:
                raise MCPServerWithNameAlreadyExistsError(
                    f"MCP server with name '{mcp_server.name}' and source "
                    f"'{mcp_server_source.value}' already exists",
                ) from e
            raise

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
            deleted_servers = [
                (row["mcp_server_id"], row["mcp_runtime_deployment_id"]) for row in rows
            ]

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
