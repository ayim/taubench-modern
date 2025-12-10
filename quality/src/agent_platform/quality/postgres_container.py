from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
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
        self._lock = asyncio.Lock()

    async def get_or_start(self, sdm_folder: Path) -> PostgresConnectionInfo:
        """Start a Postgres container for the SDM folder if needed."""
        folder_key = str(sdm_folder.resolve())
        async with self._lock:
            cached = self._containers.get(folder_key)
            if cached is not None:
                return cached.connection_info

            schema_path = sdm_folder / "schema.sql"
            seed_path = sdm_folder / "seed.sql"
            if not schema_path.exists() or not seed_path.exists():
                raise ValueError(
                    f"Missing schema.sql or seed.sql in SDM folder: {sdm_folder}",
                )

            from testcontainers.postgres import PostgresContainer

            container = (
                PostgresContainer(
                    image="postgres:16-alpine",
                )
                .with_env(
                    "POSTGRES_USER",
                    "postgres",
                )
                .with_env(
                    "POSTGRES_PASSWORD",
                    "postgres",
                )
                .with_env(
                    "POSTGRES_DB",
                    "test",
                )
            )

            await asyncio.to_thread(container.start)

            host = container.get_container_host_ip()
            port = container.get_exposed_port(container.port)
            connection_info = PostgresConnectionInfo(
                host=host,
                port=port,
                database="test",
                user="postgres",
                password="postgres",
                schema="public",
            )

            await self._initialize_database(connection_info, schema_path, seed_path)

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

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        self._containers.clear()

    async def _initialize_database(
        self,
        connection_info: PostgresConnectionInfo,
        schema_path: Path,
        seed_path: Path,
    ) -> None:
        await self._apply_sql_file(connection_info, schema_path)
        await self._apply_sql_file(connection_info, seed_path)

    async def _apply_sql_file(
        self, connection_info: PostgresConnectionInfo, sql_path: Path
    ) -> None:
        if not sql_path.exists():
            raise ValueError(f"SQL file not found: {sql_path}")

        sql_text = sql_path.read_text(encoding="utf-8")
        if not sql_text.strip():
            return

        await asyncio.to_thread(self._execute_sql, connection_info, sql_text)

    @staticmethod
    def _execute_sql(connection_info: PostgresConnectionInfo, sql_text: str) -> None:
        import psycopg
        from psycopg import sql

        with (
            psycopg.connect(
                host=connection_info.host,
                port=connection_info.port,
                dbname=connection_info.database,
                user=connection_info.user,
                password=connection_info.password,
                autocommit=True,
            ) as conn,
            conn.cursor() as cur,
        ):
            if connection_info.schema:
                cur.execute(
                    sql.SQL("SET search_path TO {}").format(sql.Identifier(connection_info.schema))
                )
            for statement in _split_sql_statements(sql_text):
                cur.execute(statement)


def _split_sql_statements(sql_text: str) -> list[bytes]:
    """Split a SQL script into individual statements, preserving order, and encoding as bytes."""
    return [
        statement.strip().encode("utf-8") for statement in sql_text.split(";") if statement.strip()
    ]
