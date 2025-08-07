import json
from typing import cast

import sqlalchemy
from sqlalchemy import MetaData, RowMapping, Table, column, delete, insert, inspect, select, update
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.types import JSON

from agent_platform.core.agent import Agent
from agent_platform.core.document_intelligence.dataserver import DIDSConnectionDetails
from agent_platform.core.document_intelligence.integrations import DocumentIntelligenceIntegration
from agent_platform.server.storage.abstract import AbstractStorage
from agent_platform.server.storage.common import CommonMixin
from agent_platform.server.storage.errors import (
    DIDSConnectionDetailsNotFoundError,
    DocumentIntelligenceIntegrationNotFoundError,
)


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
        self._metadata = MetaData()

    async def _reflect_database(self, schema=None):
        """
        Current DB reflection doesn't (currently) work with AsyncEngines,
        so we need to do it manually
        """
        if not self._engine:
            raise ValueError("Engine not initialized; call setup() first.")

        def _reflect_tables(sync_conn):
            nonlocal self
            db_inspector = cast(sqlalchemy.Inspector, inspect(sync_conn))
            for table_name in db_inspector.get_table_names(schema=schema):
                # This adds the table to the metadata object
                Table(table_name, self._metadata, autoload_with=sync_conn, schema=schema)

        async with self._engine.connect() as conn:
            await conn.run_sync(_reflect_tables)

    @staticmethod
    def as_json_columns(*column_name: str):
        """Return a JSON column for the given engine."""
        return [column(name, JSON()) for name in column_name]

    @property
    def engine(self) -> AsyncEngine:
        """Get the SQLAlchemy engine."""
        if self._engine is None:
            raise RuntimeError("Engine not initialized; call setup() first.")

        if not isinstance(self._engine, AsyncEngine):
            raise RuntimeError("Expected AsyncEngine. Found: %s", type(self._engine))

        return self._engine

    def _get_table(self, name: str) -> Table:
        return self._metadata.tables[f"{self.V2_PREFIX}{name}"]

    # -------------------------
    # Concrete convenience methods
    # -------------------------

    async def list_all_agents(self) -> list[Agent]:
        """List all agents for all users."""
        agent = self._get_table("agent")

        stmt = select(
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

    # -------------------------------------------------------------------------
    # Document Intelligence convenience methods
    # -------------------------------------------------------------------------
    async def get_dids_connection_details(self) -> DIDSConnectionDetails:
        """Get the Document Intelligence Data Server connection details."""
        dids_connection_details = self._get_table("dids_connection_details")

        stmt = select(dids_connection_details)

        async with self.engine.begin() as conn:
            result = await conn.execute(stmt)
            # We only ever store one row, so we can just fetch it
            row = result.mappings().fetchone()

        if row is None:
            raise DIDSConnectionDetailsNotFoundError()

        # Convert row to dict and handle JSON deserialization
        row_dict = dict(row)
        assert "enc_password" in row_dict, "enc_password not found"
        assert isinstance(row_dict["enc_password"], str), "enc_password is not a string"
        # Decrypt the password field
        row_dict["password"] = self._decrypt_secret_string(row_dict["enc_password"])
        row_dict.pop("enc_password")

        # Handle connections deserialization based on database type
        # SQLite stores as JSON string, PostgreSQL stores as JSONB (auto-deserialized)
        if "connections" in row_dict and isinstance(row_dict["connections"], str):
            # SQLite case: deserialize JSON string
            row_dict["connections"] = json.loads(row_dict["connections"])
        # PostgreSQL case: already deserialized by SQLAlchemy

        return DIDSConnectionDetails.model_validate(row_dict)

    async def set_dids_connection_details(self, details: DIDSConnectionDetails) -> None:
        """Set the Document Intelligence Data Server connection details."""
        dids_connection_details = self._get_table("dids_connection_details")

        async with self.engine.begin() as conn:
            # Since we only store one row, clear the table first
            delete_stmt = delete(dids_connection_details)
            await conn.execute(delete_stmt)

            details_data = {
                "username": details.username,
                "updated_at": details.updated_at,
                "connections": [conn.model_dump(mode="json") for conn in details.connections],
            }

            # Encrypt the password field for database storage
            details_data["enc_password"] = self._encrypt_secret_string(details.password)

            # Insert the new connection details
            insert_stmt = insert(dids_connection_details).values(details_data)
            await conn.execute(insert_stmt)

    async def delete_dids_connection_details(self) -> None:
        """Delete the Document Intelligence Data Server connection details."""
        dids_connection_details = self._get_table("dids_connection_details")

        async with self.engine.begin() as conn:
            # Check if connection details exist
            select_stmt = select(dids_connection_details)
            result = await conn.execute(select_stmt)
            existing_row = result.mappings().fetchone()

            if existing_row is None:
                raise DIDSConnectionDetailsNotFoundError()

            # Delete the connection details
            delete_stmt = delete(dids_connection_details)
            await conn.execute(delete_stmt)

    def _parse_di_integration_row(self, row: RowMapping) -> DocumentIntelligenceIntegration:
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

        stmt = select(integrations_table).where(integrations_table.c.kind == kind)

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

        stmt = select(integrations_table)

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
            select_stmt = select(integrations_table).where(
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
                insert_stmt = insert(integrations_table).values(integration_data)
                await conn.execute(insert_stmt)
            else:
                # Update existing integration
                update_stmt = (
                    update(integrations_table)
                    .where(integrations_table.c.kind == integration.kind)
                    .values(integration_data)
                )
                await conn.execute(update_stmt)

    async def delete_document_intelligence_integration(self, kind: str) -> None:
        """Delete a document intelligence integration by kind."""
        integrations_table = self._get_table("document_intelligence_integrations")

        async with self.engine.begin() as conn:
            # Check if integration exists
            select_stmt = select(integrations_table).where(integrations_table.c.kind == kind)
            result = await conn.execute(select_stmt)
            existing_row = result.mappings().fetchone()

            if existing_row is None:
                raise DocumentIntelligenceIntegrationNotFoundError()

            # Delete the integration
            delete_stmt = delete(integrations_table).where(integrations_table.c.kind == kind)
            await conn.execute(delete_stmt)
