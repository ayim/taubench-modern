import json
from abc import abstractmethod
from datetime import UTC, datetime, timedelta
from typing import cast

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.types import JSON

from agent_platform.core.agent import Agent
from agent_platform.core.data_frames import PlatformDataFrame
from agent_platform.core.data_server.data_server import DataServerDetails
from agent_platform.core.document_intelligence.integrations import DocumentIntelligenceIntegration
from agent_platform.server.storage.abstract import AbstractStorage
from agent_platform.server.storage.common import CommonMixin
from agent_platform.server.storage.errors import (
    DIDSConnectionDetailsNotFoundError,
    DocumentIntelligenceIntegrationNotFoundError,
)
from agent_platform.server.storage.types import StaleThreadsResult


@compiles(JSON, "postgresql")
def compile_json_as_jsonb(_type_, _compiler, **kw):
    return "JSONB"


@compiles(JSON, "sqlite")
def compile_json_as_text(_type_, _compiler, **kw):
    return "TEXT"


class BaseStorage(AbstractStorage, CommonMixin):
    """Base class for storage backends with concrete sqlalchemy and utility methods."""

    V2_PREFIX = ""  # Either v2. (postgres) or v2_ (sqlite)

    def __init__(self):
        """Initialize the storage with SQLAlchemy engine."""
        super().__init__()
        self._engine: AsyncEngine | None = None
        assert self.V2_PREFIX, "V2_PREFIX must be set"
        self._metadata = sa.MetaData()

    async def _reflect_database(self, schema=None):
        """
        Current DB reflection doesn't (currently) work with AsyncEngines,
        so we need to do it manually
        """
        if not self._engine:
            raise ValueError("Engine not initialized; call setup() first.")

        def _reflect_tables(sync_conn):
            nonlocal self
            db_inspector = cast(sa.Inspector, sa.inspect(sync_conn))
            for table_name in db_inspector.get_table_names(schema=schema):
                # This adds the table to the metadata object
                sa.Table(table_name, self._metadata, autoload_with=sync_conn, schema=schema)

        async with self._engine.connect() as conn:
            await conn.run_sync(_reflect_tables)

    @staticmethod
    def as_json_columns(*column_name: str):
        """Return a JSON column for the given engine."""
        return [sa.column(name, JSON()) for name in column_name]

    @property
    def engine(self) -> AsyncEngine:
        """Get the SQLAlchemy engine."""
        if self._engine is None:
            raise RuntimeError("Engine not initialized; call setup() first.")

        if not isinstance(self._engine, AsyncEngine):
            raise RuntimeError("Expected AsyncEngine. Found: %s", type(self._engine))

        return self._engine

    def _get_table(self, name: str) -> sa.Table:
        return self._metadata.tables[f"{self.V2_PREFIX}{name}"]

    @abstractmethod
    async def setup(self) -> None:
        """Run the migrations and any necessary setup."""

    @abstractmethod
    async def teardown(self) -> None:
        """Teardown logic, if needed."""

    @abstractmethod
    async def _run_migrations(self) -> None:
        """Run the migrations."""

    # -------------------------------------------------------------------------
    # Methods for Data Frames
    # -------------------------------------------------------------------------
    async def save_data_frame(self, data_frame: "PlatformDataFrame") -> None:
        """Save a new data frame."""
        data_frames = self._get_table("data_frames")

        # Use model_dump to properly serialize the data frame including computation_input_sources
        data_frame_dict = data_frame.model_dump()

        # Use JSON column for computation_input_sources to handle JSON serialization
        stmt = sa.insert(data_frames).values(data_frame_dict)

        async with self.engine.begin() as conn:
            await conn.execute(stmt)

    async def get_data_frame(self, data_frame_id: str) -> "PlatformDataFrame":
        """Get a data frame by ID."""
        data_frames = self._get_table("data_frames")

        stmt = (
            sa.select(
                data_frames.c.data_frame_id,
                data_frames.c.user_id,
                data_frames.c.agent_id,
                data_frames.c.thread_id,
                data_frames.c.num_rows,
                data_frames.c.num_columns,
                data_frames.c.column_headers,
                data_frames.c.name,
                data_frames.c.input_id_type,
                data_frames.c.created_at,
                data_frames.c.computation_input_sources,
                data_frames.c.file_id,
                data_frames.c.description,
                data_frames.c.computation,
                data_frames.c.parquet_contents,
                data_frames.c.sheet_name,
                data_frames.c.extra_data,
            )
            .select_from(data_frames)
            .where(data_frames.c.data_frame_id == data_frame_id)
        )

        async with self.engine.begin() as conn:
            result = await conn.execute(stmt)
            row = result.mappings().fetchone()

        if row is None:
            raise ValueError(f"Data frame {data_frame_id} not found")

        return self._build_data_frame(row)

    def _build_data_frame(self, row_mapping: sa.RowMapping) -> "PlatformDataFrame":
        # SQLAlchemy may return UUIDs as UUID objects, so we need to convert them to strings, which
        # is what we expect in the dataframe.
        row = dict(row_mapping)
        row["data_frame_id"] = str(row["data_frame_id"])
        row["user_id"] = str(row["user_id"])
        row["agent_id"] = str(row["agent_id"])
        row["thread_id"] = str(row["thread_id"])

        # Convert row to PlatformDataFrame object using model_validate for proper deserialization
        return PlatformDataFrame.model_validate(row)

    async def list_data_frames(self, thread_id: str) -> list["PlatformDataFrame"]:
        """List all data frames for a given user and thread."""
        data_frames = self._get_table("data_frames")

        stmt = (
            sa.select(
                data_frames.c.data_frame_id,
                data_frames.c.user_id,
                data_frames.c.agent_id,
                data_frames.c.thread_id,
                data_frames.c.num_rows,
                data_frames.c.num_columns,
                data_frames.c.column_headers,
                data_frames.c.name,
                data_frames.c.input_id_type,
                data_frames.c.created_at,
                data_frames.c.computation_input_sources,
                data_frames.c.file_id,
                data_frames.c.description,
                data_frames.c.computation,
                data_frames.c.parquet_contents,
                data_frames.c.sheet_name,
                data_frames.c.extra_data,
            )
            .select_from(data_frames)
            .where(data_frames.c.thread_id == thread_id)
        )

        async with self.engine.begin() as conn:
            result = await conn.execute(stmt)
            rows = result.mappings().fetchall()

        # Convert rows to PlatformDataFrame objects using model_validate for proper deserialization
        data_frames_list = []
        for row in rows:
            data_frames_list.append(self._build_data_frame(row))

        return data_frames_list

    async def delete_data_frame(self, data_frame_id: str) -> None:
        """Delete a data frame by ID."""
        data_frames = self._get_table("data_frames")

        stmt = data_frames.delete().where(data_frames.c.data_frame_id == data_frame_id)

        async with self.engine.begin() as conn:
            result = await conn.execute(stmt)
            if result.rowcount == 0:
                raise ValueError(f"Data frame {data_frame_id} not found")

    async def delete_data_frame_by_name(self, thread_id: str, data_frame_name: str) -> None:
        """Delete a data frame by ID."""
        data_frames = self._get_table("data_frames")

        stmt = (
            data_frames.delete()
            .where(data_frames.c.thread_id == thread_id)
            .where(data_frames.c.name == data_frame_name)
        )

        async with self.engine.begin() as conn:
            result = await conn.execute(stmt)
            if result.rowcount == 0:
                raise ValueError(f"Data frame {data_frame_name} not found in thread {thread_id}")

    async def update_data_frame(self, data_frame: "PlatformDataFrame") -> None:
        """Update a data frame."""
        data_frame.verify()

        data_frames = self._get_table("data_frames")

        # Use model_dump to properly serialize the data frame including computation_input_sources
        data_frame_dict = data_frame.model_dump()
        # Remove data_frame_id from the update dict since it's used in the WHERE clause
        data_frame_dict.pop("data_frame_id", None)

        stmt = (
            data_frames.update()
            .where(data_frames.c.data_frame_id == data_frame.data_frame_id)
            .values(data_frame_dict)
        )

        async with self.engine.begin() as conn:
            result = await conn.execute(stmt)
            if result.rowcount == 0:
                raise ValueError(f"Data frame {data_frame.data_frame_id} not found")

    # -------------------------
    # Concrete convenience methods
    # -------------------------

    async def list_all_agents(self) -> list[Agent]:
        """List all agents for all users."""
        agent = self._get_table("agent")

        stmt = sa.select(
            agent.c.agent_id,
            agent.c.name,
            agent.c.description,
            agent.c.user_id,
            agent.c.version,
            agent.c.created_at,
            agent.c.updated_at,
            agent.c.mode,
            *self.as_json_columns(
                "runbook_structured",
                "action_packages",
                "mcp_servers",
                "agent_architecture",
                "question_groups",
                "observability_configs",
                "platform_configs",
                "extra",
            ),
        ).select_from(agent)

        async with self.engine.begin() as conn:
            result = await conn.execute(stmt)
            rows = result.mappings().fetchall()

        # Convert rows to Agent objects
        return [Agent.model_validate(dict(row)) for row in rows]

    async def get_agent_mcp_server_ids(self, agent_id: str) -> list[str]:
        """Get MCP server IDs associated with an agent."""
        agent_mcp_server = self._get_table("agent_mcp_server")

        stmt = (
            sa.select(agent_mcp_server.c.mcp_server_id)
            .select_from(agent_mcp_server)
            .where(agent_mcp_server.c.agent_id == agent_id)
        )

        async with self.engine.begin() as conn:
            result = await conn.execute(stmt)
            rows = result.mappings().fetchall()

        return [str(row["mcp_server_id"]) for row in rows]

    async def associate_mcp_servers_with_agent(
        self, agent_id: str, mcp_server_ids: list[str]
    ) -> None:
        """Associate MCP servers with an agent."""
        agent_mcp_server = self._get_table("agent_mcp_server")

        async with self.engine.begin() as conn:
            # First, remove existing associations
            delete_stmt = sa.delete(agent_mcp_server).where(agent_mcp_server.c.agent_id == agent_id)
            await conn.execute(delete_stmt)

            # Then add new associations
            if mcp_server_ids:
                insert_data = [
                    {"agent_id": agent_id, "mcp_server_id": mcp_server_id}
                    for mcp_server_id in mcp_server_ids
                ]
                insert_stmt = sa.insert(agent_mcp_server).values(insert_data)
                await conn.execute(insert_stmt)

    # -------------------------------------------------------------------------
    # Document Intelligence convenience methods
    # -------------------------------------------------------------------------
    async def get_dids_connection_details(self) -> DataServerDetails:
        """Get the Document Intelligence Data Server connection details."""
        dids_connection_details = self._get_table("dids_connection_details")

        stmt = sa.select(dids_connection_details)

        async with self.engine.begin() as conn:
            result = await conn.execute(stmt)
            # We only ever store one row, so we can just fetch it
            row = result.mappings().fetchone()

        if row is None:
            raise DIDSConnectionDetailsNotFoundError()

        # Convert row to dict and handle JSON deserialization
        row_dict = dict(row)
        assert "enc_password" in row_dict, "enc_password not found"
        assert row_dict["enc_password"] is None or isinstance(row_dict["enc_password"], str), (
            "enc_password is not a string or None"
        )
        # Decrypt the password field
        row_dict["password"] = (
            self._decrypt_secret_string(row_dict["enc_password"])
            if row_dict["enc_password"] is not None
            else None
        )
        row_dict.pop("enc_password")

        # Handle connections deserialization based on database type
        # SQLite stores as JSON string, PostgreSQL stores as JSONB (auto-deserialized)
        # Automatically handle conversion from connections to data_server_connections
        if "data_server_endpoints" in row_dict and isinstance(
            row_dict["data_server_endpoints"], str
        ):
            # SQLite case: deserialize JSON string
            row_dict["data_server_endpoints"] = json.loads(row_dict["data_server_endpoints"])
        elif "data_server_endpoints" in row_dict and isinstance(
            row_dict["data_server_endpoints"], str
        ):
            row_dict["data_server_endpoints"] = json.loads(row_dict["data_server_endpoints"])

        return DataServerDetails.model_validate(row_dict)

    async def set_dids_connection_details(self, details: DataServerDetails) -> None:
        """Set the Document Intelligence Data Server connection details."""
        dids_connection_details = self._get_table("dids_connection_details")

        async with self.engine.begin() as conn:
            # Since we only store one row, clear the table first
            delete_stmt = sa.delete(dids_connection_details)
            await conn.execute(delete_stmt)

            details_data = {
                "username": details.username,
                "updated_at": details.updated_at,
                "data_server_endpoints": [
                    conn.model_dump(mode="json") for conn in details.data_server_endpoints
                ],
            }

            # Encrypt the password field for database storage
            details_data["enc_password"] = (
                self._encrypt_secret_string(details.password)
                if details.password is not None
                else None
            )

            # Insert the new connection details
            insert_stmt = sa.insert(dids_connection_details).values(details_data)
            await conn.execute(insert_stmt)

    async def delete_dids_connection_details(self) -> None:
        """Delete the Document Intelligence Data Server connection details."""
        dids_connection_details = self._get_table("dids_connection_details")

        async with self.engine.begin() as conn:
            # Check if connection details exist
            select_stmt = sa.select(dids_connection_details)
            result = await conn.execute(select_stmt)
            existing_row = result.mappings().fetchone()

            if existing_row is None:
                raise DIDSConnectionDetailsNotFoundError()

            # Delete the connection details
            delete_stmt = sa.delete(dids_connection_details)
            await conn.execute(delete_stmt)

    def _parse_di_integration_row(self, row: sa.RowMapping) -> DocumentIntelligenceIntegration:
        """Parse a document intelligence integration row from the database."""
        row_dict = dict(row)
        assert "enc_api_key" in row_dict, "enc_api_key not found"
        assert isinstance(row_dict["enc_api_key"], str), "enc_api_key is not a string"
        row_dict["api_key"] = self._decrypt_secret_string(row_dict["enc_api_key"])
        row_dict.pop("enc_api_key")
        return DocumentIntelligenceIntegration.model_validate(row_dict)

    async def get_document_intelligence_integration(
        self, kind: str
    ) -> DocumentIntelligenceIntegration:
        """Get a document intelligence integration by kind."""
        integrations_table = self._get_table("document_intelligence_integrations")

        stmt = sa.select(integrations_table).where(integrations_table.c.kind == kind)

        async with self.engine.begin() as conn:
            result = await conn.execute(stmt)
            row = result.mappings().fetchone()

        if row is None:
            raise DocumentIntelligenceIntegrationNotFoundError()

        return self._parse_di_integration_row(row)

    async def list_document_intelligence_integrations(
        self,
    ) -> list[DocumentIntelligenceIntegration]:
        """List all document intelligence integrations."""
        integrations_table = self._get_table("document_intelligence_integrations")

        stmt = sa.select(integrations_table)

        async with self.engine.begin() as conn:
            result = await conn.execute(stmt)
            rows = result.mappings().fetchall()

        integrations = []
        for row in rows:
            integrations.append(self._parse_di_integration_row(row))

        return integrations

    async def set_document_intelligence_integration(
        self, integration: DocumentIntelligenceIntegration
    ) -> None:
        """Create or update a document intelligence integration."""
        integrations_table = self._get_table("document_intelligence_integrations")

        async with self.engine.begin() as conn:
            # Check if integration already exists
            select_stmt = sa.select(integrations_table).where(
                integrations_table.c.kind == integration.kind
            )
            result = await conn.execute(select_stmt)
            existing_row = result.mappings().fetchone()

            integration_data = {
                "kind": integration.kind,
                "endpoint": integration.endpoint,
                "updated_at": integration.updated_at,
                "enc_api_key": self._encrypt_secret_string(integration.api_key),
            }

            if existing_row is None:
                # Insert new integration
                insert_stmt = sa.insert(integrations_table).values(integration_data)
                await conn.execute(insert_stmt)
            else:
                # Update existing integration
                update_stmt = (
                    sa.update(integrations_table)
                    .where(integrations_table.c.kind == integration.kind)
                    .values(integration_data)
                )
                await conn.execute(update_stmt)

    async def delete_document_intelligence_integration(self, kind: str) -> None:
        """Delete a document intelligence integration by kind."""
        integrations_table = self._get_table("document_intelligence_integrations")

        async with self.engine.begin() as conn:
            # Check if integration exists
            select_stmt = sa.select(integrations_table).where(integrations_table.c.kind == kind)
            result = await conn.execute(select_stmt)
            existing_row = result.mappings().fetchone()

            if existing_row is None:
                raise DocumentIntelligenceIntegrationNotFoundError()

            # Delete the integration
            delete_stmt = sa.delete(integrations_table).where(integrations_table.c.kind == kind)
            await conn.execute(delete_stmt)

    async def clean_up_stale_threads(
        self, default_retention_period: timedelta
    ) -> list[StaleThreadsResult]:
        """
        Returns:
            list[StaleThreadsResult]: A list of thread_ids that were cleaned up.
        """
        now = datetime.now(UTC)

        default_retention_datetime = now - default_retention_period

        threads = self._get_table("thread")
        configs = self._get_table("agent_config")
        files = self._get_table("file_owner")
        users = self._get_table("user")

        stale_threads_stmt = (
            sa.select(threads.c.thread_id, files.c.file_id, files.c.file_path)
            .select_from(threads)
            .join(users, threads.c.user_id == users.c.user_id)
            .outerjoin(
                configs,
                configs.c.namespace == sa.func.concat("agent_id:", threads.c.agent_id),
            )
            .outerjoin(
                files,
                threads.c.thread_id == files.c.thread_id,
            )
            .where(
                (users.c.sub.notilike("tenant:%:system:system_user"))
                & (
                    threads.c.updated_at
                    < sa.func.coalesce(
                        self._clean_up_stale_threads__get_threshold(now, configs.c.config_value),
                        default_retention_datetime,
                    )
                )
            )
        )

        async with self.engine.begin() as conn:
            result = await conn.execute(stale_threads_stmt)
            stale_threads = [StaleThreadsResult(**item) for item in result.mappings().fetchall()]

            await conn.execute(
                sa.delete(threads).where(
                    threads.c.thread_id.in_({item.thread_id for item in stale_threads})
                )
            )

        return stale_threads
