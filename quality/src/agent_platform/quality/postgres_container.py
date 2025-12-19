from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from psycopg import Connection
    from testcontainers.postgres import PostgresContainer


@dataclass
class PostgresConnectionInfo:
    host: str
    port: int
    database: str
    user: str
    password: str
    schema: str = "public"
    sslmode: str | None = None


@dataclass
class _ContainerHandle:
    container: PostgresContainer
    connection_info: PostgresConnectionInfo


class PostgresContainerManager:
    """Manages testcontainer Postgres instances."""

    def __init__(self):
        self._containers: dict[str, _ContainerHandle] = {}
        self._connections: dict[str, Connection] = {}
        self._lock = asyncio.Lock()
        self._log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

    async def get_or_start(self, sdm_folder: Path) -> PostgresConnectionInfo:
        """Start a Postgres container for the SDM folder if needed."""
        folder_key = str(sdm_folder.resolve())
        async with self._lock:
            cached = self._containers.get(folder_key)
            if cached is not None:
                self._log.debug(
                    "postgres_container.cache_hit",
                    folder_key=folder_key,
                    host=cached.connection_info.host,
                    port=cached.connection_info.port,
                )
                return cached.connection_info

            schema_path = sdm_folder / "schema.sql"
            seed_path = sdm_folder / "seed.sql"
            if not schema_path.exists() or not seed_path.exists():
                raise ValueError(
                    f"Missing schema.sql or seed.sql in SDM folder: {sdm_folder}",
                )

            from testcontainers.postgres import PostgresContainer

            container = PostgresContainer(
                image="postgres:18-alpine",
                username="postgres",
                password="postgres",
                dbname="test",
            )

            self._log.info(
                "postgres_container.starting",
                folder_key=folder_key,
                image=container.image,
                username=container.username,
                dbname=container.dbname,
            )
            await asyncio.to_thread(container.start)

            host = container.get_container_host_ip()
            port = int(container.get_exposed_port(container.port))
            self._log.info(
                "postgres_container.started",
                folder_key=folder_key,
                host=host,
                port=port,
                dbname=container.dbname,
                username=container.username,
            )
            connection_info = PostgresConnectionInfo(
                host=host,
                port=port,
                database=container.dbname,
                user=container.username,
                password=container.password,
                schema="public",
            )

            await self._initialize_database(folder_key, connection_info, schema_path, seed_path)

            self._containers[folder_key] = _ContainerHandle(
                container=container,
                connection_info=connection_info,
            )
            return connection_info

    async def cleanup_all(self) -> None:
        """Stop all running containers."""
        tasks = []
        for handle in self._containers.values():
            tasks.append(asyncio.to_thread(handle.container.stop))

        for connection in list(self._connections.values()):
            tasks.append(asyncio.to_thread(connection.close))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self._containers.clear()
        self._connections.clear()

    async def _initialize_database(
        self,
        folder_key: str,
        connection_info: PostgresConnectionInfo,
        schema_path: Path,
        seed_path: Path,
    ) -> None:
        await self._apply_sql_file(folder_key, connection_info, schema_path)
        await self._apply_sql_file(folder_key, connection_info, seed_path)

    async def _apply_sql_file(
        self,
        folder_key: str,
        connection_info: PostgresConnectionInfo,
        sql_path: Path,
    ) -> None:
        if not sql_path.exists():
            raise ValueError(f"SQL file not found: {sql_path}")

        sql_text = sql_path.read_text(encoding="utf-8")
        if not sql_text.strip():
            return

        connection = await self._get_connection(folder_key, connection_info)
        await asyncio.to_thread(self._execute_sql, connection, connection_info, sql_text)

    @staticmethod
    def _execute_sql(connection: Connection, connection_info: PostgresConnectionInfo, sql_text: str) -> None:
        from psycopg import sql

        log = structlog.get_logger(__name__)
        statements = _split_sql_statements(sql_text)
        try:
            with connection.cursor() as cur:
                if connection_info.schema:
                    cur.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(connection_info.schema)))
                for statement in statements:
                    cur.execute(statement)
        except Exception:
            log.exception(
                "postgres_container.execute_sql_failed",
                host=connection_info.host,
                port=connection_info.port,
                database=connection_info.database,
                user=connection_info.user,
            )
            raise

    async def _get_connection(self, folder_key: str, connection_info: PostgresConnectionInfo) -> Connection:
        cached = self._connections.get(folder_key)
        if cached is not None and not cached.closed:
            return cached

        def _connect() -> Connection:
            import psycopg

            return psycopg.connect(
                host=connection_info.host,
                port=connection_info.port,
                dbname=connection_info.database,
                user=connection_info.user,
                password=connection_info.password,
                autocommit=True,
            )

        connection = await asyncio.to_thread(_connect)
        self._connections[folder_key] = connection
        return connection


def _split_sql_statements(sql_text: str) -> list[bytes]:
    """Split a SQL script into individual statements, preserving order, and encoding as bytes.

    Properly handles:
    - String literals (single quotes) with escaped quotes ('')
    - Semicolons inside string literals
    - Comments are kept as part of statements
    """
    statements = []
    current_statement = []
    in_string = False
    i = 0

    while i < len(sql_text):
        char = sql_text[i]

        # Track string literal state
        if char == "'" and not in_string:
            in_string = True
            current_statement.append(char)
        elif char == "'" and in_string:
            # Check if this is an escaped quote ('')
            if i + 1 < len(sql_text) and sql_text[i + 1] == "'":
                current_statement.append("''")
                i += 1  # Skip the next quote
            else:
                # End of string literal
                in_string = False
                current_statement.append(char)
        elif char == ";" and not in_string:
            # Statement terminator outside of string - split here
            stmt = "".join(current_statement).strip()
            if stmt:
                statements.append(stmt.encode("utf-8"))
            current_statement = []
        else:
            current_statement.append(char)

        i += 1

    # Add final statement if exists
    final_stmt = "".join(current_statement).strip()
    if final_stmt:
        statements.append(final_stmt.encode("utf-8"))

    return statements
