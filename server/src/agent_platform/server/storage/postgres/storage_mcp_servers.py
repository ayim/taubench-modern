import uuid
from datetime import UTC, datetime

from psycopg.errors import UniqueViolation
from psycopg.sql import SQL
from structlog import get_logger

from agent_platform.core.mcp.mcp_server import MCPServer, MCPServerSource
from agent_platform.server.storage.common import CommonMixin
from agent_platform.server.storage.errors import (
    ConfigDecryptionError,
    MCPServerNotFoundError,
    MCPServerWithNameAlreadyExistsError,
    RecordAlreadyExistsError,
)
from agent_platform.server.storage.postgres.cursor import CursorMixin


class PostgresStorageMCPServersMixin(CursorMixin, CommonMixin):
    """Mixin for PostgreSQL MCP server operations."""

    _logger = get_logger(__name__)

    async def create_mcp_server(self, mcp_server: MCPServer, source: MCPServerSource) -> str:
        """Create a new MCP server. Returns the generated MCP server ID."""
        # 1. Generate ID and timestamps
        mcp_server_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        # 2. Prepare the config as encrypted JSONB (secret manager returns structured JSON)
        config_dict = mcp_server.model_dump()
        encrypted_config = self._encrypt_config(config_dict)

        # 3. Insert the MCP server
        try:
            async with self._cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO v2.mcp_server (
                        mcp_server_id, name, enc_config, source, created_at, updated_at
                    )
                    VALUES (
                        %s::uuid, %s, %s, %s, %s, %s
                    )
                    """,
                    (mcp_server_id, mcp_server.name, encrypted_config, source.value, now, now),
                )
        except UniqueViolation as e:
            if "mcp_server_pkey" in str(e):
                raise RecordAlreadyExistsError(
                    f"MCP server {mcp_server_id} already exists",
                ) from e
            elif "idx_mcp_server_name_source" in str(e):
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

        async with self._cursor() as cur:
            # 2. Get the MCP server
            await cur.execute(
                """
                SELECT enc_config::text AS enc_config FROM v2.mcp_server
                WHERE mcp_server_id = %s::uuid
                """,
                (mcp_server_id,),
            )

            # 3. No MCP server found?
            if not (row := await cur.fetchone()):
                raise MCPServerNotFoundError(f"MCP server {mcp_server_id} not found")

            # 4. Decrypt and return the MCP server from enc_config
            encrypted_config = row["enc_config"]
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
                SELECT enc_config::text AS enc_config, source FROM v2.mcp_server
                WHERE mcp_server_id = %s::uuid
                """,
                (mcp_server_id,),
            )

            # 3. No MCP server found?
            if not (row := await cur.fetchone()):
                raise MCPServerNotFoundError(f"MCP server {mcp_server_id} not found")

            # 4. Decrypt and return the MCP server and source
            encrypted_config = row["enc_config"]
            try:
                config_dict = self._decrypt_config(encrypted_config)
                mcp_server = MCPServer.model_validate(config_dict)
                source = MCPServerSource(row["source"])
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
                SELECT mcp_server_id, enc_config::text AS enc_config, source FROM v2.mcp_server
                ORDER BY created_at DESC
                """,
            )

            # 3. No MCP servers found?
            if not (rows := await cur.fetchall()):
                return {}

            # 4. Decrypt and return the MCP servers as a dict of id -> (MCPServer, MCPServerSource)
            result = {}
            for row in rows:
                server_id = str(row["mcp_server_id"])
                encrypted_config = row["enc_config"]
                try:
                    config_dict = self._decrypt_config(encrypted_config)
                    mcp_server = MCPServer.model_validate(config_dict)
                    source = MCPServerSource(row["source"])
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
                    f"Failed to decrypt MCP server configuration for '{name}' with source "
                    f"'{source.value}'"
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

    async def get_mcp_servers_by_ids(self, mcp_server_ids: list[str]) -> dict[str, MCPServer]:
        """Get multiple MCP servers by their IDs."""
        if not mcp_server_ids:
            return {}

        # Validate all UUIDs
        for mcp_server_id in mcp_server_ids:
            self._validate_uuid(mcp_server_id)

        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT mcp_server_id, enc_config::text AS enc_config FROM v2.mcp_server
                WHERE mcp_server_id = ANY(%s::uuid[])
                """,
                (mcp_server_ids,),
            )

            rows = await cur.fetchall()
            result = {}
            for row in rows:
                server_id = row["mcp_server_id"]
                encrypted_config = row["enc_config"]
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

        # 2. Prepare the config as encrypted text
        config_dict = mcp_server.model_dump()
        encrypted_config = self._encrypt_config(config_dict)

        now = datetime.now(UTC)

        # 3. Update the MCP server
        try:
            async with self._cursor() as cur:
                await cur.execute(
                    """
                    UPDATE v2.mcp_server
                    SET
                        name = %s,
                        enc_config = %s,
                        source = %s,
                        updated_at = %s
                    WHERE mcp_server_id = %s::uuid
                    RETURNING mcp_server_id
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
                if not await cur.fetchone():
                    raise MCPServerNotFoundError(f"MCP server {mcp_server_id} not found")
        except UniqueViolation as e:
            if "idx_mcp_server_name_source" in str(e):
                raise MCPServerWithNameAlreadyExistsError(
                    f"MCP server with name '{mcp_server.name}' and source "
                    f"'{mcp_server_source.value}' already exists",
                ) from e
            raise

    async def delete_mcp_server(self, mcp_server_ids: list[str]) -> None:
        """Delete one or more MCP servers."""
        # 1. Validate all uuids
        for server_id in mcp_server_ids:
            self._validate_uuid(server_id)

        if not mcp_server_ids:
            return

        async with self._cursor() as cur:
            # 2. Delete the MCP servers
            # Create placeholders for the IN clause
            placeholders = SQL(",").join([SQL("%s::uuid")] * len(mcp_server_ids))
            query = SQL("""
                DELETE FROM v2.mcp_server
                WHERE mcp_server_id IN ({placeholders})
                RETURNING mcp_server_id
                """).format(placeholders=placeholders)
            await cur.execute(query, mcp_server_ids)

            # 3. Check if all deletes succeeded
            deleted_ids = [str(row["mcp_server_id"]) for row in await cur.fetchall()]
            missing_ids = set(mcp_server_ids) - set(deleted_ids)
            if missing_ids:
                raise MCPServerNotFoundError(f"MCP servers not found: {', '.join(missing_ids)}")

    async def count_mcp_servers(self) -> int:
        """Count the number of MCP servers."""
        async with self._cursor() as cur:
            await cur.execute("SELECT COUNT(*) AS cnt FROM v2.mcp_server")
            if not (row := await cur.fetchone()):
                return 0

            return row["cnt"]
