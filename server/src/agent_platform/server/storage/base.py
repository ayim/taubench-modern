import asyncio
import dataclasses
import json
import typing
from abc import abstractmethod
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import TracebackType
from typing import Any, Protocol, TypedDict, cast, runtime_checkable

import sqlalchemy as sa
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.types import JSON, DateTime, TypeDecorator
from structlog.stdlib import get_logger

from agent_platform.core.agent import Agent
from agent_platform.core.data_connections.data_connections import DataConnection
from agent_platform.core.data_frames import PlatformDataFrame
from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel
from agent_platform.core.errors import ErrorCode, PlatformHTTPError
from agent_platform.core.evals.types import (
    EvaluationResult,
    ExecutionState,
    Scenario,
    ScenarioBatchRun,
    ScenarioBatchRunStatistics,
    ScenarioBatchRunStatus,
    ScenarioRun,
    Trial,
    TrialStatus,
)
from agent_platform.core.integrations import Integration, IntegrationScope
from agent_platform.core.integrations.observability.integration import ObservabilityIntegration
from agent_platform.core.thread import ThreadMessage
from agent_platform.server.storage.abstract import AbstractStorage
from agent_platform.server.storage.common import CommonMixin
from agent_platform.server.storage.errors import (
    DataConnectionNotFoundError,
    DIDSConnectionDetailsNotFoundError,
    IntegrationNotFoundError,
    IntegrationScopeNotFoundError,
    InvalidScopeError,
    TrialAlreadyCanceledError,
    TrialNotFoundError,
)

if typing.TYPE_CHECKING:
    from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

    from agent_platform.server.oauth.oauth_provider import OAuthCallbackResult
    from agent_platform.server.storage.types import StaleThreadsResult


logger = get_logger(__name__)


@runtime_checkable
class AsyncLockLike(Protocol):
    """API for an async-io lock which can only be used as a context manager."""

    async def __aenter__(self) -> "AsyncLockLike": ...
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool | None: ...


@compiles(JSON, "postgresql")
def compile_json_as_jsonb(_type_, _compiler, **kw):
    return "JSONB"


@compiles(JSON, "sqlite")
def compile_json_as_text(_type_, _compiler, **kw):
    return "TEXT"


class ISO8601DateTime(TypeDecorator):
    """Custom DateTime type that ensures ISO8601 format for SQLite.

    SQLAlchemy's default DateTime handling for SQLite uses a space separator
    (e.g., '2024-12-10 17:09:32.500537') instead of ISO8601's 'T' separator
    (e.g., '2024-12-10T17:09:32.500537').

    This TypeDecorator ensures consistent ISO8601 formatting across all database
    backends by converting Python datetime objects to ISO8601 strings before
    binding them as parameters for SQLite, while using native datetime handling
    for Postgres.

    Usage:
        When explicitly defining table columns, use this type instead of DateTime:

        ```python
        table = sa.Table(
            'my_table',
            metadata,
            sa.Column('created_at', ISO8601DateTime, nullable=False),
        )
        ```

    Note: The current codebase uses table reflection, so this TypeDecorator is
    not applied to reflected columns. Instead, sqlite.py monkey-patches the
    SQLAlchemy DateTime.bind_processor method during engine setup to ensure
    ISO8601 formatting for all datetime parameters (both column values and
    literal values in WHERE clauses).

    This TypeDecorator exists for:
    1. Future-proofing if we migrate to explicit table definitions
    2. Documentation of the datetime formatting requirements
    3. Use in explicit table definitions if needed
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Convert datetime to ISO8601 string for SQLite, native for Postgres."""
        if value is not None and dialect.name == "sqlite":
            return value.isoformat()
        return value

    def process_result_value(self, value, dialect):
        """Convert ISO8601 string back to datetime for SQLite, native for Postgres.

        Note: SQLite stores datetimes as TEXT, so we need to parse them back.
        """
        if value is not None and dialect.name == "sqlite" and isinstance(value, str):
            # Handle both with and without microseconds
            if "." in value:
                return datetime.fromisoformat(value)
            else:
                return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S")
        return value


class BaseStorage(AbstractStorage, CommonMixin):
    """Base class for storage backends with concrete sqlalchemy and utility methods."""

    V2_PREFIX = ""  # Either v2. (postgres) or v2_ (sqlite)

    _write_lock: AsyncLockLike  # Subclasses must set this

    def __init__(self):
        """Initialize the storage with SQLAlchemy engine."""
        super().__init__()
        self.__sa_engine: AsyncEngine | None = None
        assert self.V2_PREFIX, "V2_PREFIX must be set"
        self._metadata = sa.MetaData()

    async def _reflect_database(self, schema=None):
        """
        Current DB reflection doesn't (currently) work with AsyncEngines,
        so we need to do it manually
        """
        if not self.__sa_engine:
            raise ValueError("Engine not initialized; call setup() first.")

        def _reflect_tables(sync_conn):
            nonlocal self
            db_inspector = cast(sa.Inspector, sa.inspect(sync_conn))
            for table_name in db_inspector.get_table_names(schema=schema):
                # This adds the table to the metadata object
                sa.Table(table_name, self._metadata, autoload_with=sync_conn, schema=schema)

        async with self.__sa_engine.connect() as conn:
            await conn.run_sync(_reflect_tables)

    @staticmethod
    def as_json_columns(*column_name: str):
        """Return a JSON column for the given engine."""
        return [sa.column(name, JSON()) for name in column_name]

    @property
    def _sa_engine(self) -> AsyncEngine:
        """Get the SQLAlchemy engine."""
        if self.__sa_engine is None:
            raise RuntimeError("Engine not initialized; call setup() first.")

        if not isinstance(self.__sa_engine, AsyncEngine):
            raise RuntimeError("Expected AsyncEngine. Found: %s", type(self.__sa_engine))

        return self.__sa_engine

    @_sa_engine.setter
    def _sa_engine(self, value: AsyncEngine):
        # Subclasses must set it on 'setup'
        self.__sa_engine = value

    # Note: engine and _engine are deprecated. Use _sa_engine instead.
    # Not declaring it here at all so that typecheck can get it.

    @asynccontextmanager
    async def _write_connection(self) -> AsyncIterator[AsyncConnection]:
        """
        Acquire the write lock and open a transactional connection.
        Commits on success, rolls back on exception.
        """
        async with self._write_lock:
            async with self._sa_engine.begin() as conn:
                yield conn

    @asynccontextmanager
    async def _read_connection(self) -> AsyncIterator[AsyncConnection]:
        """
        Open a read-only connection.
        """
        async with self._sa_engine.connect() as conn:
            yield conn

    def _get_table(self, name: str) -> sa.Table:
        return self._metadata.tables[f"{self.V2_PREFIX}{name}"]

    @abstractmethod
    async def setup(self) -> None:
        """Run the migrations and any necessary setup."""

    async def teardown(self) -> None:
        """Disposes of the SQLAlchemy engine."""
        try:
            sa_engine = self.__sa_engine
        except AttributeError:
            pass
        else:
            if sa_engine is not None:
                await sa_engine.dispose()
            self.__sa_engine = None

    @abstractmethod
    async def _run_migrations(self) -> None:
        """Run the migrations."""

    @abstractmethod
    async def apply_pool_size(self, new_max: int) -> None:
        """Resize psycopg pool to the new pool size.

        Validates against current psycopg min_size. On invalid values, raises
        PlatformHTTPError with BAD_REQUEST.

        On SQLite, this is a no-op.
        """

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

        async with self._write_connection() as conn:
            await conn.execute(stmt)

    async def get_data_frame(
        self, thread_id: str, data_frame_id: str | None = None, data_frame_name: str | None = None
    ) -> "PlatformDataFrame":
        """Get a data frame by ID."""
        from agent_platform.core.errors.base import PlatformHTTPError
        from agent_platform.core.errors.responses import ErrorCode

        data_frames = self._get_table("data_frames")

        stmt = sa.select(
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
        ).select_from(data_frames)

        stmt = stmt.where(data_frames.c.thread_id == thread_id)

        if data_frame_id is not None:
            stmt = stmt.where(data_frames.c.data_frame_id == data_frame_id)
        elif data_frame_name is not None:
            stmt = stmt.where(data_frames.c.name == data_frame_name)
        else:
            raise ValueError("Either data_frame_id or data_frame_name must be provided")

        async with self._read_connection() as conn:
            result = await conn.execute(stmt)
            row = result.mappings().fetchone()

        if row is None:
            if data_frame_name is not None:
                raise PlatformHTTPError(
                    error_code=ErrorCode.NOT_FOUND,
                    message=f"Data frame with name {data_frame_name} not found in thread: {thread_id}",
                )
            elif data_frame_id is not None:
                raise PlatformHTTPError(
                    error_code=ErrorCode.NOT_FOUND,
                    message=f"Data frame with id {data_frame_id} not found in thread: {thread_id}",
                )
            else:
                raise ValueError("Either data_frame_id or data_frame_name must be provided")
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

        async with self._read_connection() as conn:
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

        async with self._write_connection() as conn:
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

        async with self._write_connection() as conn:
            result = await conn.execute(stmt)
            if result.rowcount == 0:
                raise ValueError(f"Data frame {data_frame_name} not found in thread {thread_id}")

    async def update_data_frame(self, data_frame: "PlatformDataFrame") -> None:
        """Update a data frame."""
        from agent_platform.core.errors.base import PlatformHTTPError
        from agent_platform.core.errors.responses import ErrorCode

        data_frame.verify()

        data_frames = self._get_table("data_frames")

        # Use model_dump to properly serialize the data frame including computation_input_sources
        data_frame_dict = data_frame.model_dump()
        # Remove data_frame_id from the update dict since it's used in the WHERE clause
        data_frame_dict.pop("data_frame_id", None)

        stmt = (
            data_frames.update().where(data_frames.c.data_frame_id == data_frame.data_frame_id).values(data_frame_dict)
        )

        async with self._write_connection() as conn:
            result = await conn.execute(stmt)
            if result.rowcount == 0:
                raise PlatformHTTPError(
                    error_code=ErrorCode.NOT_FOUND,
                    message=f"Data frame {data_frame.data_frame_id} not found",
                )

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
                "selected_tools",
            ),
        ).select_from(agent)

        async with self._read_connection() as conn:
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

        async with self._read_connection() as conn:
            result = await conn.execute(stmt)
            rows = result.mappings().fetchall()

            return [str(row["mcp_server_id"]) for row in rows]

    async def get_agent_platform_params_ids(self, agent_id: str) -> list[str]:
        """Get platform params IDs associated with an agent."""
        agent_platform_params = self._get_table("agent_platform_params")

        stmt = (
            sa.select(agent_platform_params.c.platform_params_id)
            .select_from(agent_platform_params)
            .where(agent_platform_params.c.agent_id == agent_id)
        )

        async with self._read_connection() as conn:
            result = await conn.execute(stmt)
            rows = result.mappings().fetchall()

        return [str(row["platform_params_id"]) for row in rows]

    async def associate_mcp_servers_with_agent(self, agent_id: str, mcp_server_ids: list[str]) -> None:
        """Associate MCP servers with an agent."""
        agent_mcp_server = self._get_table("agent_mcp_server")

        async with self._write_connection() as conn:
            # First, remove existing associations
            delete_stmt = sa.delete(agent_mcp_server).where(agent_mcp_server.c.agent_id == agent_id)
            await conn.execute(delete_stmt)

            # Then add new associations
            if mcp_server_ids:
                insert_data = [
                    {"agent_id": agent_id, "mcp_server_id": mcp_server_id} for mcp_server_id in mcp_server_ids
                ]
                insert_stmt = sa.insert(agent_mcp_server).values(insert_data)
                await conn.execute(insert_stmt)

    # -------------------------------------------------------------------------
    # Agent Data Connections
    # -------------------------------------------------------------------------
    async def get_agent_data_connection_ids(self, agent_id: str) -> list[str]:
        """Get data connection IDs associated with an agent."""
        agent_data_connections = self._get_table("agent_data_connections")

        stmt = (
            sa.select(agent_data_connections.c.data_connection_id)
            .select_from(agent_data_connections)
            .where(agent_data_connections.c.agent_id == agent_id)
        )

        async with self._read_connection() as conn:
            result = await conn.execute(stmt)
            rows = result.mappings().fetchall()

        return [str(row["data_connection_id"]) for row in rows]

    async def set_agent_data_connections(self, agent_id: str, data_connection_ids: list[str]) -> None:
        """Set data connections for an agent (replace all existing associations)."""
        agent_data_connections = self._get_table("agent_data_connections")

        async with self._write_connection() as conn:
            # First, remove existing associations
            delete_stmt = sa.delete(agent_data_connections).where(agent_data_connections.c.agent_id == agent_id)
            await conn.execute(delete_stmt)

            # Then add new associations
            if data_connection_ids:
                insert_data = [
                    {"agent_id": agent_id, "data_connection_id": data_connection_id}
                    for data_connection_id in data_connection_ids
                ]
                insert_stmt = sa.insert(agent_data_connections).values(insert_data)
                await conn.execute(insert_stmt)

    async def get_agent_data_connections(self, agent_id: str) -> list["DataConnection"]:
        """Get data connections associated with an agent."""
        # Get the data connection IDs first
        data_connection_ids = await self.get_agent_data_connection_ids(agent_id)

        if not data_connection_ids:
            return []

        # Get the actual data connections
        data_connections = self._get_table("data_connection")
        stmt = sa.select(data_connections).where(data_connections.c.id.in_(data_connection_ids))

        async with self._read_connection() as conn:
            result = await conn.execute(stmt)
            rows = result.mappings().fetchall()

        decrypted_rows = []
        for row in rows:
            row_dict = dict(row)
            row_dict["configuration"] = self._decrypt_config(row_dict["enc_configuration"])
            decrypted_rows.append(row_dict)

        return [DataConnection.model_validate(row_dict) for row_dict in decrypted_rows]

    # -------------------------------------------------------------------------
    # Document Intelligence convenience methods
    # -------------------------------------------------------------------------
    async def delete_dids_connection_details(self) -> None:
        """Delete the Document Intelligence Data Server connection details."""
        dids_connection_details = self._get_table("dids_connection_details")

        async with self._write_connection() as conn:
            # Check if connection details exist
            select_stmt = sa.select(dids_connection_details)
            result = await conn.execute(select_stmt)
            existing_row = result.mappings().fetchone()

            if existing_row is None:
                raise DIDSConnectionDetailsNotFoundError()

            # Delete the connection details
            delete_stmt = sa.delete(dids_connection_details)
            await conn.execute(delete_stmt)

    async def clean_up_stale_threads(self, default_retention_period: timedelta) -> "list[StaleThreadsResult]":
        """
        Returns:
            list[StaleThreadsResult]: A list of thread_ids that were cleaned up.
        """
        from agent_platform.server.storage.types import StaleThreadsResult

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

        async with self._write_connection() as conn:
            result = await conn.execute(stale_threads_stmt)
            stale_threads = [StaleThreadsResult(**item) for item in result.mappings().fetchall()]

            await conn.execute(
                sa.delete(threads).where(threads.c.thread_id.in_({item.thread_id for item in stale_threads}))
            )

        return stale_threads

    async def create_scenario(self, scenario: Scenario) -> Scenario:
        """Create a new scenario."""
        scenarios = self._get_table("scenarios")

        async with self._write_connection() as conn:
            scenario_dict = scenario.model_dump()

            insert_stmt = (
                sa.insert(scenarios)
                .values(scenario_dict)
                .returning(
                    scenarios.c.scenario_id,
                    scenarios.c.name,
                    scenarios.c.description,
                    scenarios.c.thread_id,
                    scenarios.c.agent_id,
                    scenarios.c.user_id,
                    scenarios.c.created_at,
                    scenarios.c.updated_at,
                    scenarios.c.messages,
                    scenarios.c.metadata,
                )
            )
            result = await conn.execute(insert_stmt)
            row = result.mappings().fetchone()

            if row is None:
                raise RuntimeError("Cannot insert scenario")

            return Scenario.model_validate(dict(row))

    async def update_scenario_messages(
        self,
        scenario_id: str,
        messages: list[ThreadMessage],
    ) -> Scenario:
        """Update the messages for an existing scenario."""
        scenarios = self._get_table("scenarios")
        payload = {
            "messages": [message.model_dump() for message in messages],
            "updated_at": datetime.now(UTC).isoformat(),
        }

        async with self._write_connection() as conn:
            update_stmt = (
                sa.update(scenarios)
                .where(scenarios.c.scenario_id == scenario_id)
                .values(payload)
                .returning(
                    scenarios.c.scenario_id,
                    scenarios.c.name,
                    scenarios.c.description,
                    scenarios.c.thread_id,
                    scenarios.c.agent_id,
                    scenarios.c.user_id,
                    scenarios.c.created_at,
                    scenarios.c.updated_at,
                    scenarios.c.messages,
                    scenarios.c.metadata,
                )
            )
            result = await conn.execute(update_stmt)
            row = result.mappings().fetchone()

        if row is None:
            raise RuntimeError(f"Scenario {scenario_id} not found")

        return Scenario.model_validate(dict(row))

    async def list_scenarios(
        self, limit: int | None, agent_id: str | None, include_messages: bool = False
    ) -> list[Scenario]:
        """List all scenarios.

        Args:
            limit: Maximum number of scenarios to return
            agent_id: Filter by agent ID
            include_messages: If True, include full message history (default: False for performance)

        Note: Messages are excluded by default for performance. Set include_messages=True
        when you need the full conversation history (e.g., for exports).
        """
        scenarios = self._get_table("scenarios")

        # Build column list - conditionally include messages
        columns = [
            scenarios.c.scenario_id,
            scenarios.c.name,
            scenarios.c.description,
            scenarios.c.thread_id,
            scenarios.c.agent_id,
            scenarios.c.user_id,
            scenarios.c.created_at,
            scenarios.c.updated_at,
            scenarios.c.metadata,
        ]

        if include_messages:
            columns.insert(8, scenarios.c.messages)  # Insert before metadata

        stmt = sa.select(*columns).select_from(scenarios)

        if agent_id is not None:
            stmt = stmt.where(scenarios.c.agent_id == agent_id)

        if limit is not None:
            stmt = stmt.limit(limit)

        async with self._read_connection() as conn:
            result = await conn.execute(stmt)
            rows = result.mappings().fetchall()

        # If messages weren't loaded, set to empty list
        if not include_messages:
            return [Scenario.model_validate({**dict(row), "messages": []}) for row in rows]

        return [Scenario.model_validate(dict(row)) for row in rows]

    async def get_scenario(self, scenario_id: str) -> Scenario | None:
        """Get a scenario."""
        scenarios = self._get_table("scenarios")

        stmt = sa.select(
            scenarios.c.scenario_id,
            scenarios.c.name,
            scenarios.c.description,
            scenarios.c.thread_id,
            scenarios.c.agent_id,
            scenarios.c.user_id,
            scenarios.c.created_at,
            scenarios.c.updated_at,
            scenarios.c.messages,
            scenarios.c.metadata,
        ).where(scenarios.c.scenario_id == scenario_id)

        async with self._read_connection() as conn:
            result = await conn.execute(stmt)
            row = result.mappings().fetchone()

        return Scenario.model_validate(dict(row)) if row is not None else None

    async def update_scenario(self, scenario: Scenario) -> Scenario:
        """Update a scenario."""
        scenarios = self._get_table("scenarios")

        stmt = (
            sa.update(scenarios)
            .where(scenarios.c.scenario_id == scenario.scenario_id)
            .values(
                name=scenario.name,
                description=scenario.description,
                metadata=scenario.metadata,
                updated_at=scenario.updated_at,
            )
            .returning(
                scenarios.c.scenario_id,
                scenarios.c.name,
                scenarios.c.description,
                scenarios.c.thread_id,
                scenarios.c.agent_id,
                scenarios.c.user_id,
                scenarios.c.created_at,
                scenarios.c.updated_at,
                scenarios.c.messages,
                scenarios.c.metadata,
            )
        )

        async with self._write_connection() as conn:
            result = await conn.execute(stmt)
            row = result.mappings().fetchone()

        if row is None:
            raise RuntimeError("Cannot update scenario")

        return Scenario.model_validate(dict(row))

    async def delete_scenario(self, scenario_id: str) -> Scenario | None:
        """Delete a scenario."""
        scenarios = self._get_table("scenarios")

        stmt = (
            sa.delete(scenarios)
            .where(scenarios.c.scenario_id == scenario_id)
            .returning(
                scenarios.c.scenario_id,
                scenarios.c.name,
                scenarios.c.description,
                scenarios.c.thread_id,
                scenarios.c.agent_id,
                scenarios.c.user_id,
                scenarios.c.created_at,
                scenarios.c.updated_at,
                scenarios.c.messages,
                scenarios.c.metadata,
            )
        )

        async with self._write_connection() as conn:
            result = await conn.execute(stmt)
            row = result.mappings().fetchone()

        return Scenario.model_validate(dict(row)) if row is not None else None

    async def create_scenario_run(self, scenario_run: ScenarioRun) -> ScenarioRun:
        scenario_runs = self._get_table("scenario_runs")
        trials = self._get_table("trials")

        async with self._write_connection() as conn:
            run_dict = scenario_run.model_dump()
            trials_dicts = [trial.model_dump() for trial in scenario_run.trials]

            insert_run_stmt = (
                sa.insert(scenario_runs)
                .values(run_dict)
                .returning(
                    scenario_runs.c.scenario_run_id,
                    scenario_runs.c.scenario_id,
                    scenario_runs.c.user_id,
                    scenario_runs.c.batch_run_id,
                    scenario_runs.c.num_trials,
                    scenario_runs.c.configuration,
                    scenario_runs.c.created_at,
                )
            )
            result = await conn.execute(insert_run_stmt)
            run_row = result.mappings().fetchone()

            if run_row is None:
                raise RuntimeError("Cannot insert scenario run")

            insert_trials_stmt = (
                sa.insert(trials)
                .values(trials_dicts)
                .returning(
                    trials.c.trial_id,
                    trials.c.scenario_run_id,
                    trials.c.scenario_id,
                    trials.c.thread_id,
                    trials.c.index_in_run,
                    trials.c.status,
                    trials.c.created_at,
                    trials.c.updated_at,
                    trials.c.status_updated_at,
                    trials.c.status_updated_by,
                    trials.c.error_message,
                    trials.c.metadata,
                    trials.c.retry_after_at,
                    trials.c.reschedule_attempts,
                )
            )

            trial_result = await conn.execute(insert_trials_stmt)
            trial_rows = trial_result.mappings().all()

            run_dict = dict(run_row)
            trial_dicts = [dict(t) for t in trial_rows]

            run_dict["trials"] = trial_dicts

            return ScenarioRun.model_validate(run_dict)

    async def get_scenario_run(self, scenario_run_id: str) -> ScenarioRun | None:
        """Get a scenario run."""
        scenario_runs = self._get_table("scenario_runs")
        trials = self._get_table("trials")

        get_run_stmt = sa.select(
            scenario_runs.c.scenario_run_id,
            scenario_runs.c.scenario_id,
            scenario_runs.c.user_id,
            scenario_runs.c.batch_run_id,
            scenario_runs.c.num_trials,
            scenario_runs.c.configuration,
            scenario_runs.c.created_at,
        ).where(scenario_runs.c.scenario_run_id == scenario_run_id)

        get_trials_per_run = sa.select(
            trials.c.trial_id,
            trials.c.scenario_run_id,
            trials.c.scenario_id,
            trials.c.thread_id,
            trials.c.index_in_run,
            trials.c.status,
            trials.c.created_at,
            trials.c.updated_at,
            trials.c.status_updated_at,
            trials.c.status_updated_by,
            trials.c.error_message,
            trials.c.evaluation_results,
            trials.c.execution_state,
            trials.c.metadata,
            trials.c.retry_after_at,
            trials.c.reschedule_attempts,
        ).where(trials.c.scenario_run_id == scenario_run_id)

        async with self._read_connection() as conn:
            result = await conn.execute(get_run_stmt)
            run_row = result.mappings().fetchone()

            result = await conn.execute(get_trials_per_run)
            trials_rows = result.mappings().fetchall()

        if run_row is None:
            return None

        run_dict = dict(run_row)
        trial_dicts = [dict(trial_row) for trial_row in trials_rows]

        run_dict["trials"] = trial_dicts

        return ScenarioRun.model_validate(run_dict)

    async def list_scenario_runs(self, scenario_id: str, limit: int | None) -> list[ScenarioRun]:
        """List all scenario runs."""
        scenario_runs = self._get_table("scenario_runs")

        stmt = (
            sa.select(
                scenario_runs.c.scenario_run_id,
                scenario_runs.c.scenario_id,
                scenario_runs.c.user_id,
                scenario_runs.c.batch_run_id,
                scenario_runs.c.num_trials,
                scenario_runs.c.configuration,
                scenario_runs.c.created_at,
            )
            .select_from(scenario_runs)
            .where(scenario_runs.c.scenario_id == scenario_id)
            .order_by(scenario_runs.c.created_at.desc())
            .limit(limit)
        )

        async with self._read_connection() as conn:
            result = await conn.execute(stmt)
            rows = result.mappings().fetchall()

        return [ScenarioRun.model_validate(dict(row)) for row in rows]

    async def list_scenario_runs_for_batch(self, batch_run_id: str) -> list[ScenarioRun]:
        """List all scenario runs associated with a batch."""
        scenario_runs = self._get_table("scenario_runs")

        stmt = (
            sa.select(
                scenario_runs.c.scenario_run_id,
                scenario_runs.c.scenario_id,
                scenario_runs.c.user_id,
                scenario_runs.c.batch_run_id,
                scenario_runs.c.num_trials,
                scenario_runs.c.configuration,
                scenario_runs.c.created_at,
            )
            .where(scenario_runs.c.batch_run_id == batch_run_id)
            .order_by(scenario_runs.c.created_at.asc())
        )

        async with self._read_connection() as conn:
            result = await conn.execute(stmt)
            rows = result.mappings().fetchall()

        return [ScenarioRun.model_validate(dict(row)) for row in rows]

    async def create_scenario_batch_run(self, batch_run: ScenarioBatchRun) -> ScenarioBatchRun:
        """Persist a new scenario batch run."""
        batches = self._get_table("scenario_run_batches")
        values = batch_run.model_dump()
        # trial_statuses are derived dynamically and not persisted in the DB schema
        values.pop("trial_statuses", None)
        stmt = (
            sa.insert(batches)
            .values(values)
            .returning(
                batches.c.batch_run_id,
                batches.c.agent_id,
                batches.c.user_id,
                batches.c.metadata,
                batches.c.scenario_ids,
                batches.c.status,
                batches.c.statistics,
                batches.c.created_at,
                batches.c.updated_at,
                batches.c.completed_at,
            )
        )

        async with self._write_connection() as conn:
            result = await conn.execute(stmt)
            row = result.mappings().fetchone()

        if row is None:
            raise RuntimeError("Cannot insert scenario batch run")

        return ScenarioBatchRun.model_validate(dict(row))

    async def get_scenario_batch_run(self, batch_run_id: str) -> ScenarioBatchRun | None:
        """Retrieve a scenario batch run by id."""
        batches = self._get_table("scenario_run_batches")
        stmt = sa.select(
            batches.c.batch_run_id,
            batches.c.agent_id,
            batches.c.user_id,
            batches.c.metadata,
            batches.c.scenario_ids,
            batches.c.status,
            batches.c.statistics,
            batches.c.created_at,
            batches.c.updated_at,
            batches.c.completed_at,
        ).where(batches.c.batch_run_id == batch_run_id)

        async with self._read_connection() as conn:
            result = await conn.execute(stmt)
            row = result.mappings().fetchone()

        return ScenarioBatchRun.model_validate(dict(row)) if row is not None else None

    async def update_scenario_batch_run(
        self,
        batch_run_id: str,
        *,
        status: ScenarioBatchRunStatus | None = None,
        statistics: ScenarioBatchRunStatistics | None = None,
        completed_at: datetime | None = None,
    ) -> ScenarioBatchRun | None:
        """Update status/statistics of a scenario batch run."""
        if not any([status, statistics, completed_at]):
            return await self.get_scenario_batch_run(batch_run_id)

        batches = self._get_table("scenario_run_batches")
        values: dict[str, Any] = {"updated_at": datetime.now(UTC)}
        if status is not None:
            values["status"] = status.value
        if statistics is not None:
            values["statistics"] = statistics.model_dump()
        if completed_at is not None:
            values["completed_at"] = completed_at

        stmt = (
            sa.update(batches)
            .where(batches.c.batch_run_id == batch_run_id)
            .values(values)
            .returning(
                batches.c.batch_run_id,
                batches.c.agent_id,
                batches.c.user_id,
                batches.c.metadata,
                batches.c.scenario_ids,
                batches.c.status,
                batches.c.statistics,
                batches.c.created_at,
                batches.c.updated_at,
                batches.c.completed_at,
            )
        )

        async with self._write_connection() as conn:
            result = await conn.execute(stmt)
            row = result.mappings().fetchone()

        return ScenarioBatchRun.model_validate(dict(row)) if row is not None else None

    async def list_scenario_batch_runs(self, agent_id: str, limit: int | None = None) -> list[ScenarioBatchRun]:
        """List batch runs for a given agent."""
        batches = self._get_table("scenario_run_batches")
        stmt = (
            sa.select(
                batches.c.batch_run_id,
                batches.c.agent_id,
                batches.c.user_id,
                batches.c.metadata,
                batches.c.scenario_ids,
                batches.c.status,
                batches.c.statistics,
                batches.c.created_at,
                batches.c.updated_at,
                batches.c.completed_at,
            )
            .where(batches.c.agent_id == agent_id)
            .order_by(batches.c.created_at.desc())
            .limit(limit)
        )

        async with self._read_connection() as conn:
            result = await conn.execute(stmt)
            rows = result.mappings().fetchall()

        return [ScenarioBatchRun.model_validate(dict(row)) for row in rows]

    async def get_active_scenario_batch_run(self, agent_id: str) -> ScenarioBatchRun | None:
        """Return the most recent non-terminal batch run for an agent, if any."""
        batches = self._get_table("scenario_run_batches")
        active_statuses = (
            ScenarioBatchRunStatus.PENDING.value,
            ScenarioBatchRunStatus.RUNNING.value,
        )

        stmt = (
            sa.select(
                batches.c.batch_run_id,
                batches.c.agent_id,
                batches.c.user_id,
                batches.c.metadata,
                batches.c.scenario_ids,
                batches.c.status,
                batches.c.statistics,
                batches.c.created_at,
                batches.c.updated_at,
                batches.c.completed_at,
            )
            .where(
                sa.and_(
                    batches.c.agent_id == agent_id,
                    batches.c.status.in_(active_statuses),
                )
            )
            .order_by(batches.c.created_at.desc())
            .limit(1)
        )

        async with self._read_connection() as conn:
            result = await conn.execute(stmt)
            row = result.mappings().fetchone()

        return ScenarioBatchRun.model_validate(dict(row)) if row is not None else None

    async def list_scenario_run_trials(self, scenario_run_id: str) -> list[Trial]:
        """Get a run trial."""
        trials = self._get_table("trials")

        columns = [
            trials.c.trial_id,
            trials.c.scenario_run_id,
            trials.c.scenario_id,
            trials.c.thread_id,
            trials.c.index_in_run,
            trials.c.status,
            trials.c.created_at,
            trials.c.updated_at,
            trials.c.status_updated_at,
            trials.c.status_updated_by,
            trials.c.error_message,
            trials.c.evaluation_results,
            trials.c.execution_state,
            trials.c.metadata,
            trials.c.retry_after_at,
            trials.c.reschedule_attempts,
        ]

        stmt = sa.select(*columns).where(trials.c.scenario_run_id == scenario_run_id)

        async with self._read_connection() as conn:
            result = await conn.execute(stmt)
            rows = result.mappings().fetchall()

        return [Trial.model_validate(dict(row)) for row in rows]

    async def get_scenario_run_trial(self, scenario_run_id: str, trial_index: int) -> Trial | None:
        """Get a run trial."""
        trials = self._get_table("trials")

        columns = [
            trials.c.trial_id,
            trials.c.scenario_run_id,
            trials.c.scenario_id,
            trials.c.index_in_run,
            trials.c.thread_id,
            trials.c.status,
            trials.c.created_at,
            trials.c.updated_at,
            trials.c.status_updated_at,
            trials.c.status_updated_by,
            trials.c.error_message,
            trials.c.evaluation_results,
            trials.c.execution_state,
            trials.c.metadata,
            trials.c.retry_after_at,
            trials.c.reschedule_attempts,
        ]
        stmt = sa.select(*columns).where(
            sa.and_(trials.c.scenario_run_id == scenario_run_id, trials.c.index_in_run == trial_index)
        )

        async with self._read_connection() as conn:
            result = await conn.execute(stmt)
            row = result.mappings().fetchone()

        return Trial.model_validate(dict(row)) if row is not None else None

    async def set_trial_thread(self, trial_id: str, thread_id: str):
        trials = self._get_table("trials")

        insert_stmt = (
            sa.update(trials)
            .where(trials.c.trial_id == trial_id)
            .values(
                thread_id=thread_id,
            )
        )

        async with self._write_connection() as conn:
            await conn.execute(insert_stmt)

    async def get_pending_trial_ids(self, limit: int = 10) -> list[str]:
        """Atomically claim a batch of PENDING trials and mark them EXECUTING."""
        trials = self._get_table("trials")
        now = datetime.now(UTC)
        eligible = sa.and_(
            trials.c.status == TrialStatus.PENDING,
            sa.or_(trials.c.retry_after_at.is_(None), trials.c.retry_after_at <= now),
        )
        pending_trial_ids = (
            sa.select(trials.c.trial_id)
            .where(eligible)
            .order_by(sa.func.coalesce(trials.c.retry_after_at, trials.c.created_at).asc())
            .limit(limit)
            .subquery()
        )

        claim_stmt = (
            sa.update(trials)
            .where(
                sa.and_(
                    trials.c.trial_id.in_(sa.select(pending_trial_ids.c.trial_id)),
                    trials.c.status == TrialStatus.PENDING,
                )
            )
            .values(
                status=TrialStatus.EXECUTING,
                updated_at=now,
                status_updated_at=now,
                retry_after_at=None,
            )
            .returning(
                trials.c.trial_id,
            )
        )

        async with self._write_connection() as conn:
            result = await conn.execute(claim_stmt)
            rows = result.mappings().fetchall()

        return [str(row["trial_id"]) for row in rows]

    async def get_trials_by_ids(self, trials_ids: list[str]) -> list[Trial]:
        """Retrieve multiple trials given their IDs."""
        trials = self._get_table("trials")
        columns = [
            trials.c.trial_id,
            trials.c.scenario_run_id,
            trials.c.scenario_id,
            trials.c.index_in_run,
            trials.c.thread_id,
            trials.c.status,
            trials.c.created_at,
            trials.c.updated_at,
            trials.c.status_updated_at,
            trials.c.status_updated_by,
            trials.c.error_message,
            trials.c.evaluation_results,
            trials.c.execution_state,
            trials.c.metadata,
            trials.c.retry_after_at,
            trials.c.reschedule_attempts,
        ]
        get_trials_by_ids = sa.select(*columns).where(trials.c.trial_id.in_(trials_ids))

        async with self._read_connection() as conn:
            result = await conn.execute(get_trials_by_ids)
            rows = result.mappings().fetchall()

        return [Trial.model_validate(dict(row)) for row in rows]

    async def get_trial(self, trial_id: str) -> Trial | None:
        trials = self._get_table("trials")
        columns = [
            trials.c.trial_id,
            trials.c.scenario_run_id,
            trials.c.scenario_id,
            trials.c.index_in_run,
            trials.c.thread_id,
            trials.c.status,
            trials.c.created_at,
            trials.c.updated_at,
            trials.c.status_updated_at,
            trials.c.status_updated_by,
            trials.c.error_message,
            trials.c.evaluation_results,
            trials.c.execution_state,
            trials.c.metadata,
            trials.c.retry_after_at,
            trials.c.reschedule_attempts,
        ]
        get_trials_by_ids = sa.select(*columns).where(trials.c.trial_id == trial_id)

        async with self._read_connection() as conn:
            result = await conn.execute(get_trials_by_ids)
            row = result.mappings().fetchone()

            if not row:
                return None

        return Trial.model_validate(dict(row))

    async def mark_trials_as_failed(self, trial_ids: list[str], error: str | None = None):
        trials = self._get_table("trials")
        now = datetime.now(UTC)

        update_trials_stmt = (
            sa.update(trials)
            .where(trials.c.trial_id.in_(trial_ids))
            .values(
                status=TrialStatus.ERROR,
                error_message=error,
                updated_at=now,
                status_updated_at=now,
            )
            .returning(
                trials.c.trial_id,
            )
        )

        async with self._write_connection() as conn:
            result = await conn.execute(update_trials_stmt)
            rows = result.mappings().fetchall()

        return [row["trial_id"] for row in rows]

    async def update_trial_status(self, trial_id: str, user_id: str, status: TrialStatus, error: str | None = None):
        trials = self._get_table("trials")
        now = datetime.now(UTC)

        update_trials_stmt = (
            sa.update(trials)
            .where(trials.c.trial_id == trial_id)
            .values(
                status=status,
                error_message=error,
                updated_at=now,
                status_updated_at=now,
                retry_after_at=None,
            )
            .returning(
                trials.c.trial_id,
            )
        )

        async with self._write_connection() as conn:
            result = await conn.execute(update_trials_stmt)
            row = result.mappings().fetchone()

        return row["trial_id"] if row is not None else None

    async def update_trial_status_if_not_canceled(
        self, trial_id: str, user_id: str, status: TrialStatus, error: str | None = None
    ):
        trials = self._get_table("trials")
        now = datetime.now(UTC)

        update_trials_stmt = (
            sa.update(trials)
            .where(trials.c.trial_id == trial_id, trials.c.status != TrialStatus.CANCELED)
            .values(
                status=status,
                error_message=error,
                updated_at=now,
                status_updated_at=now,
                retry_after_at=None,
            )
            .returning(
                trials.c.trial_id,
            )
        )

        async with self._write_connection() as conn:
            result = await conn.execute(update_trials_stmt)
            row = result.mappings().fetchone()

            if row is not None:
                return row["trial_id"]

            # No row updated: figure out if it's because it's canceled, or missing.
            status_row = await conn.execute(sa.select(trials.c.status).where(trials.c.trial_id == trial_id))
            status_value = status_row.scalar_one_or_none()

            if status_value is None:
                raise TrialNotFoundError(f"Trial {trial_id!r} not found")

            if status_value == TrialStatus.CANCELED:
                raise TrialAlreadyCanceledError(f"Trial {trial_id!r} is already canceled")

    async def update_trial_evaluation_results(self, trial_id: str, evaluations: Sequence[EvaluationResult]):
        trials = self._get_table("trials")
        now = datetime.now(UTC)

        evals_data = [e.model_dump() for e in evaluations]
        update_trials_stmt = (
            sa.update(trials)
            .where(trials.c.trial_id == trial_id)
            .values(
                evaluation_results=evals_data,
                updated_at=now,
            )
            .returning(
                trials.c.trial_id,
            )
        )

        async with self._write_connection() as conn:
            result = await conn.execute(update_trials_stmt)
            row = result.mappings().fetchone()

        return row["trial_id"] if row is not None else None

    async def requeue_trial(
        self,
        trial_id: str,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
        retry_after_at: datetime | None = None,
        reschedule_attempts: int | None = None,
    ) -> str | None:
        trials = self._get_table("trials")
        now = datetime.now(UTC)
        default_execution_state = ExecutionState().model_dump()

        values: dict[str, Any] = {
            "status": TrialStatus.PENDING,
            "error_message": reason,
            "thread_id": None,
            "evaluation_results": [],
            "execution_state": default_execution_state,
            "updated_at": now,
            "status_updated_at": now,
            "retry_after_at": retry_after_at,
        }
        if metadata is not None:
            values["metadata"] = metadata
        if reschedule_attempts is not None:
            values["reschedule_attempts"] = reschedule_attempts

        stmt = (
            sa.update(trials)
            .where(
                sa.and_(
                    trials.c.trial_id == trial_id,
                    trials.c.status == TrialStatus.EXECUTING,
                )
            )
            .values(**values)
            .returning(trials.c.trial_id)
        )

        async with self._write_connection() as conn:
            result = await conn.execute(stmt)
            row = result.mappings().fetchone()

        return row["trial_id"] if row is not None else None

    async def update_trial_execution(self, trial_id: str, execution: ExecutionState):
        trials = self._get_table("trials")
        now = datetime.now(UTC)

        update_trials_stmt = (
            sa.update(trials)
            .where(trials.c.trial_id == trial_id)
            .values(
                execution_state=execution.model_dump(),
                updated_at=now,
            )
            .returning(
                trials.c.trial_id,
            )
        )

        async with self._write_connection() as conn:
            result = await conn.execute(update_trials_stmt)
            row = result.mappings().fetchone()

        return row["trial_id"] if row is not None else None

    # -------------------------------------------------------------------------
    # Data Connections getter and setter
    # -------------------------------------------------------------------------
    async def get_data_connections(self, data_connection_ids: list[str] | None = None) -> list["DataConnection"]:
        """Get all data connections."""
        data_connections = self._get_table("data_connection")

        stmt = sa.select(data_connections)

        if data_connection_ids:
            stmt = stmt.where(data_connections.c.id.in_(data_connection_ids))

        async with self._read_connection() as conn:
            result = await conn.execute(stmt)
            rows = result.mappings().fetchall()

        decrypted_rows = []
        for row in rows:
            row_dict = dict(row)
            row_dict["configuration"] = self._decrypt_config(row_dict["enc_configuration"])

            # Parse tags JSON string back to list for SQLite compatibility
            if self._sa_engine.dialect.name == "sqlite" and isinstance(row_dict.get("tags"), str):
                row_dict["tags"] = json.loads(row_dict["tags"]) if row_dict["tags"] else []

            decrypted_rows.append(row_dict)

        return [DataConnection.model_validate(row_dict) for row_dict in decrypted_rows]

    async def get_data_connection(self, connection_id: str) -> DataConnection:
        """Get data connection by ID."""
        data_connections = self._get_table("data_connection")
        async with self._read_connection() as conn:
            result = await conn.execute(sa.select(data_connections).where(data_connections.c.id == connection_id))
            row = result.mappings().fetchone()
            if row is None:
                raise DataConnectionNotFoundError(connection_id)
        row_dict = dict(row)
        row_dict["configuration"] = self._decrypt_config(row_dict["enc_configuration"])
        row_dict.pop("enc_configuration")

        # Parse tags JSON string back to list for SQLite compatibility
        if self._sa_engine.dialect.name == "sqlite" and isinstance(row_dict.get("tags"), str):
            row_dict["tags"] = json.loads(row_dict["tags"]) if row_dict["tags"] else []

        return DataConnection.model_validate(row_dict)

    async def get_data_connection_by_name(self, name: str) -> DataConnection | None:
        """Get data connection by name (case-insensitive). Returns None if not found."""
        data_connections = self._get_table("data_connection")
        async with self._read_connection() as conn:
            result = await conn.execute(
                sa.select(data_connections).where(sa.func.lower(data_connections.c.name) == name.lower())
            )
            row = result.mappings().fetchone()
            if row is None:
                return None

        row_dict = dict(row)
        row_dict["configuration"] = self._decrypt_config(row_dict["enc_configuration"])
        row_dict.pop("enc_configuration")

        # Parse tags JSON string back to list for SQLite compatibility
        if self._sa_engine.dialect.name == "sqlite" and isinstance(row_dict.get("tags"), str):
            row_dict["tags"] = json.loads(row_dict["tags"]) if row_dict["tags"] else []

        return DataConnection.model_validate(row_dict)

    async def set_data_connection(self, data_connection: DataConnection) -> None:
        """Set data connections."""
        data_connections = self._get_table("data_connection")
        data_connection_dict = data_connection.model_dump()
        data_connection_dict["enc_configuration"] = self._encrypt_config(data_connection_dict["configuration"])
        data_connection_dict.pop("configuration")

        # Convert tags list to JSON string for SQLite compatibility
        if self._sa_engine.dialect.name == "sqlite":
            data_connection_dict["tags"] = json.dumps(data_connection_dict["tags"])

        async with self._write_connection() as conn:
            await conn.execute(sa.insert(data_connections).values(data_connection_dict))

    async def delete_data_connection(self, connection_id: str) -> None:
        """Delete data connection."""
        data_connections = self._get_table("data_connection")
        async with self._write_connection() as conn:
            result = await conn.execute(sa.delete(data_connections).where(data_connections.c.id == connection_id))
            if result.rowcount == 0:
                raise DataConnectionNotFoundError(connection_id)

    async def update_data_connection(self, data_connection: DataConnection) -> None:
        """Update data connections."""
        data_connections = self._get_table("data_connection")
        data_connection_dict = data_connection.model_dump()
        data_connection_dict["enc_configuration"] = self._encrypt_config(data_connection_dict["configuration"])
        data_connection_dict.pop("configuration")
        data_connection_dict["updated_at"] = datetime.now(UTC)

        # Convert tags list to JSON string for SQLite compatibility
        if self._sa_engine.dialect.name == "sqlite":
            data_connection_dict["tags"] = json.dumps(data_connection_dict["tags"])

        async with self._write_connection() as conn:
            await conn.execute(
                sa.update(data_connections)
                .where(data_connections.c.id == data_connection.id)
                .values(data_connection_dict)
            )

    async def add_data_connection_tag(self, connection_id: str, tag: str) -> None:
        """Add a tag to a data connection."""
        data_connections = self._get_table("data_connection")
        async with self._write_connection() as conn:
            # First get the current tags
            result = await conn.execute(
                sa.select(data_connections.c.tags).where(data_connections.c.id == connection_id)
            )
            row = result.fetchone()
            if not row:
                raise DataConnectionNotFoundError(connection_id)

            tags_raw = row[0] or []
            # Parse tags from JSON string for SQLite compatibility
            if self._sa_engine.dialect.name == "sqlite" and isinstance(tags_raw, str):
                current_tags = json.loads(tags_raw) if tags_raw else []
            else:
                current_tags = tags_raw or []

            if tag not in current_tags:
                current_tags.append(tag)

            # Update with new tags
            tags_value = json.dumps(current_tags) if self._sa_engine.dialect.name == "sqlite" else current_tags
            await conn.execute(
                sa.update(data_connections)
                .where(data_connections.c.id == connection_id)
                .values(tags=tags_value, updated_at=datetime.now(UTC))
            )

    async def remove_data_connection_tag(self, connection_id: str, tag: str) -> None:
        """Remove a tag from a data connection."""
        data_connections = self._get_table("data_connection")
        async with self._write_connection() as conn:
            # First get the current tags
            result = await conn.execute(
                sa.select(data_connections.c.tags).where(data_connections.c.id == connection_id)
            )
            row = result.fetchone()
            if not row:
                raise DataConnectionNotFoundError(connection_id)

            tags_raw = row[0] or []
            # Parse tags from JSON string for SQLite compatibility
            if self._sa_engine.dialect.name == "sqlite" and isinstance(tags_raw, str):
                current_tags = json.loads(tags_raw) if tags_raw else []
            else:
                current_tags = tags_raw or []

            if tag in current_tags:
                current_tags.remove(tag)

            # Update with new tags
            tags_value = json.dumps(current_tags) if self._sa_engine.dialect.name == "sqlite" else current_tags
            await conn.execute(
                sa.update(data_connections)
                .where(data_connections.c.id == connection_id)
                .values(tags=tags_value, updated_at=datetime.now(UTC))
            )

    async def get_data_connections_by_tag(self, tag: str) -> list[DataConnection]:
        """Get all data connections that have a specific tag."""
        data_connections = self._get_table("data_connection")
        async with self._read_connection() as conn:
            if self._sa_engine.dialect.name == "postgresql":
                result = await conn.execute(sa.select(data_connections).where(data_connections.c.tags.contains([tag])))
            else:  # sqlite
                result = await conn.execute(
                    sa.select(data_connections).where(data_connections.c.tags.contains(f'"{tag}"'))
                )

            rows = result.mappings().fetchall()

        decrypted_rows = []
        for row in rows:
            row_dict = dict(row)
            row_dict["configuration"] = self._decrypt_config(row_dict["enc_configuration"])

            # Parse tags JSON string back to list for SQLite compatibility
            if self._sa_engine.dialect.name == "sqlite" and isinstance(row_dict.get("tags"), str):
                row_dict["tags"] = json.loads(row_dict["tags"]) if row_dict["tags"] else []

            decrypted_rows.append(row_dict)

        return [DataConnection.model_validate(row_dict) for row_dict in decrypted_rows]

    async def clear_data_connection_tag(self, tag: str) -> None:
        """Remove a specific tag from all data connections."""
        all_data_connections = await self.get_data_connections()
        for connection in all_data_connections:
            if tag in connection.tags:
                await self.remove_data_connection_tag(connection.id, tag)

    # -------------------------------------------------------------------------
    # Methods for Semantic Data Models
    # -------------------------------------------------------------------------

    async def update_semantic_data_model(
        self,
        semantic_data_model_id: str,
        semantic_model: SemanticDataModel | dict,
    ) -> None:
        """Update a semantic data model with a promise that the data connections and file references
        won't change (so, references tables will not be updated, just the semantic model itself)."""
        semantic_data_models = self._get_table("semantic_data_model")

        # For PostgreSQL: pass dict directly to JSONB (SQLAlchemy auto-serializes)
        # For SQLite: must use json.dumps (SQLite doesn't support dict binding)
        semantic_model_value = (
            json.dumps(semantic_model) if self._sa_engine.dialect.name == "sqlite" else semantic_model
        )
        async with self._write_connection() as conn:
            await conn.execute(
                sa.update(semantic_data_models)
                .where(semantic_data_models.c.id == semantic_data_model_id)
                .values(semantic_model=semantic_model_value, updated_at=datetime.now(UTC))
            )

    async def set_semantic_data_model(
        self,
        semantic_data_model_id: str | None,
        semantic_model: SemanticDataModel | dict,
        data_connection_ids: list[str],
        file_references: list[tuple[str, str]],  # (thread_id, file_ref)
    ) -> str:
        """Set a semantic data model with its input data connections and file references
        and return the ID of the semantic data model."""
        import uuid

        semantic_data_models = self._get_table("semantic_data_model")
        input_data_connections = self._get_table("semantic_data_model_input_data_connections")
        input_file_references = self._get_table("semantic_data_model_input_file_references")

        # Note: there's currently no validation at all here!
        async with self._write_connection() as conn:
            # For PostgreSQL: pass dict directly to JSONB (SQLAlchemy auto-serializes)
            # For SQLite: must use json.dumps (SQLite doesn't support dict binding)
            semantic_model_value = (
                json.dumps(semantic_model) if self._sa_engine.dialect.name == "sqlite" else semantic_model
            )

            if semantic_data_model_id is None:
                semantic_data_model_id = str(uuid.uuid4())

                # Insert the semantic data model
                insert_stmt = sa.insert(semantic_data_models).values(
                    id=semantic_data_model_id,
                    semantic_model=semantic_model_value,
                    updated_at=datetime.now(UTC),
                )

                await conn.execute(insert_stmt)
            else:
                # Clear existing associations
                task1 = conn.execute(
                    sa.delete(input_data_connections).where(
                        input_data_connections.c.semantic_data_model_id == semantic_data_model_id
                    )
                )
                task2 = conn.execute(
                    sa.delete(input_file_references).where(
                        input_file_references.c.semantic_data_model_id == semantic_data_model_id
                    )
                )
                await asyncio.gather(task1, task2)

                # The upsert is database-specific (so, we need to use the proper dialect
                # in order to do the on_conflict_update, even though it's the same thing).
                if self._sa_engine.dialect.name == "sqlite":
                    from sqlalchemy.dialects.sqlite import insert
                else:
                    from sqlalchemy.dialects.postgresql import insert

                upsert_stmt = insert(semantic_data_models).values(
                    id=semantic_data_model_id,
                    semantic_model=semantic_model_value,
                    updated_at=datetime.now(UTC),
                )

                # Update (or insert) the semantic data model
                upsert_stmt = upsert_stmt.on_conflict_do_update(
                    index_elements=[semantic_data_models.c.id],
                    set_={
                        "semantic_model": upsert_stmt.excluded.semantic_model,
                        "updated_at": upsert_stmt.excluded.updated_at,
                    },
                )

                await conn.execute(upsert_stmt)

            # Add new data connection associations
            if data_connection_ids:
                insert_data_connections = [
                    {
                        "semantic_data_model_id": semantic_data_model_id,
                        "data_connection_id": conn_id,
                    }
                    for conn_id in data_connection_ids
                ]
                await conn.execute(sa.insert(input_data_connections).values(insert_data_connections))

            # Add new file reference associations
            if file_references:
                insert_file_references = [
                    {
                        "semantic_data_model_id": semantic_data_model_id,
                        "thread_id": thread_id,
                        "file_ref": file_ref,
                    }
                    for thread_id, file_ref in file_references
                ]
                await conn.execute(sa.insert(input_file_references).values(insert_file_references))

        return semantic_data_model_id

    async def get_semantic_data_model(self, semantic_data_model_id: str) -> dict:
        """Get a semantic data model by ID."""
        from agent_platform.core.errors.base import PlatformHTTPError
        from agent_platform.core.errors.responses import ErrorCode

        semantic_data_models = self._get_table("semantic_data_model")

        async with self._read_connection() as conn:
            result = await conn.execute(
                sa.select(semantic_data_models).where(semantic_data_models.c.id == semantic_data_model_id)
            )
            row = result.mappings().fetchone()
            if row is None:
                raise PlatformHTTPError(
                    error_code=ErrorCode.NOT_FOUND,
                    message=f"Semantic data model with ID {semantic_data_model_id} not found",
                )

        # PostgreSQL: SQLAlchemy returns JSONB as dict (no parsing needed)
        # SQLite: SQLAlchemy returns TEXT as string (needs json.loads)
        semantic_model = row["semantic_model"]

        # Parse if string (SQLite normal, or PostgreSQL legacy double-serialized)
        if isinstance(semantic_model, str):
            semantic_model = json.loads(semantic_model)

        return semantic_model

    async def delete_semantic_data_model(self, semantic_data_model_id: str) -> None:
        """Delete a semantic data model by ID."""
        from agent_platform.core.errors.base import PlatformHTTPError
        from agent_platform.core.errors.responses import ErrorCode

        semantic_data_models = self._get_table("semantic_data_model")

        async with self._write_connection() as conn:
            result = await conn.execute(
                sa.delete(semantic_data_models).where(semantic_data_models.c.id == semantic_data_model_id)
            )
            if result.rowcount == 0:
                raise PlatformHTTPError(
                    error_code=ErrorCode.NOT_FOUND,
                    message=f"Semantic data model with ID {semantic_data_model_id} not found",
                )

    # -------------------------------------------------------------------------
    # Methods for Agent Semantic Data Models
    # -------------------------------------------------------------------------
    async def set_agent_semantic_data_models(self, agent_id: str, semantic_data_model_ids: list[str]) -> None:
        """Set semantic data models for an agent (replace all existing associations)."""
        agent_semantic_data_models = self._get_table("agent_semantic_data_models")

        async with self._write_connection() as conn:
            # First, remove existing associations
            delete_stmt = sa.delete(agent_semantic_data_models).where(agent_semantic_data_models.c.agent_id == agent_id)
            await conn.execute(delete_stmt)

            # Then add new associations
            if semantic_data_model_ids:
                insert_data = [
                    {"agent_id": agent_id, "semantic_data_model_id": semantic_data_model_id}
                    for semantic_data_model_id in semantic_data_model_ids
                ]
                insert_stmt = sa.insert(agent_semantic_data_models).values(insert_data)
                await conn.execute(insert_stmt)

    async def get_agent_semantic_data_models(self, agent_id: str) -> list[dict]:
        """Get semantic data models associated with an agent."""
        from agent_platform.core.errors.base import PlatformHTTPError
        from agent_platform.core.errors.responses import ErrorCode

        # Get the semantic data model IDs first
        semantic_data_model_ids = await self.get_agent_semantic_data_model_ids(agent_id)

        if not semantic_data_model_ids:
            return []

        # Get the semantic data models
        semantic_data_models = []
        for semantic_data_model_id in semantic_data_model_ids:
            try:
                semantic_data_model = await self.get_semantic_data_model(semantic_data_model_id)
                semantic_data_models.append({semantic_data_model_id: semantic_data_model})
            except PlatformHTTPError as e:
                if e.response.code == ErrorCode.NOT_FOUND.code:
                    continue
                raise e
            except ValueError:
                # Skip if semantic data model doesn't exist
                continue

        return semantic_data_models

    async def get_agent_semantic_data_model_ids(self, agent_id: str) -> list[str]:
        """Get semantic data model IDs associated with an agent."""
        agent_semantic_data_models = self._get_table("agent_semantic_data_models")

        async with self._read_connection() as conn:
            stmt = sa.select(agent_semantic_data_models.c.semantic_data_model_id).where(
                agent_semantic_data_models.c.agent_id == agent_id
            )
            result = await conn.execute(stmt)
            rows = result.mappings().fetchall()

        return [str(row["semantic_data_model_id"]) for row in rows]

    # -------------------------------------------------------------------------
    # Methods for Thread Semantic Data Models
    # -------------------------------------------------------------------------
    async def set_thread_semantic_data_models(self, thread_id: str, semantic_data_model_ids: list[str]) -> None:
        """Set semantic data models for a thread (replace all existing associations)."""
        thread_semantic_data_models = self._get_table("thread_semantic_data_models")

        async with self._write_connection() as conn:
            # First, remove existing associations
            delete_stmt = sa.delete(thread_semantic_data_models).where(
                thread_semantic_data_models.c.thread_id == thread_id
            )
            await conn.execute(delete_stmt)

            # Then add new associations
            if semantic_data_model_ids:
                insert_data = [
                    {"thread_id": thread_id, "semantic_data_model_id": semantic_data_model_id}
                    for semantic_data_model_id in semantic_data_model_ids
                ]
                insert_stmt = sa.insert(thread_semantic_data_models).values(insert_data)
                await conn.execute(insert_stmt)

    async def get_thread_semantic_data_models(self, thread_id: str) -> list[dict]:
        """Get semantic data models associated with a thread."""
        # Get the semantic data model IDs first
        semantic_data_model_ids = await self.get_thread_semantic_data_model_ids(thread_id)

        if not semantic_data_model_ids:
            return []

        # Get the semantic data models
        semantic_data_models = []
        for semantic_data_model_id in semantic_data_model_ids:
            try:
                semantic_data_model = await self.get_semantic_data_model(semantic_data_model_id)
                semantic_data_models.append({semantic_data_model_id: semantic_data_model})
            except ValueError:
                # Skip if semantic data model doesn't exist
                continue

        return semantic_data_models

    async def get_thread_semantic_data_model_ids(self, thread_id: str) -> list[str]:
        """Get semantic data model IDs associated with a thread."""
        thread_semantic_data_models = self._get_table("thread_semantic_data_models")

        async with self._read_connection() as conn:
            stmt = sa.select(thread_semantic_data_models.c.semantic_data_model_id).where(
                thread_semantic_data_models.c.thread_id == thread_id
            )
            result = await conn.execute(stmt)
            rows = result.mappings().fetchall()

        return [str(row["semantic_data_model_id"]) for row in rows]

    # -------------------------------------------------------------------------
    # Methods for Integrations
    # -------------------------------------------------------------------------
    async def upsert_integration(self, integration: Integration) -> None:
        """Update (or insert) an integration.

        For observability integrations, automatically assigns global scope
        if no scopes exist. This ensures the integration works out of the box.
        """
        integrations = self._get_table("integration")
        integration_dict = integration.model_dump()

        # Normalize optional fields
        integration_dict["description"] = integration_dict.get("description")
        integration_dict["version"] = integration_dict.get("version")

        # Encrypt the settings
        integration_dict["enc_settings"] = self._encrypt_config(integration_dict["settings"])
        integration_dict.pop("settings")

        # Update timestamp
        integration_dict["updated_at"] = datetime.now(UTC)

        async with self._write_connection() as conn:
            # Import the appropriate insert class based on dialect
            if self._sa_engine.dialect.name == "sqlite":
                from sqlalchemy.dialects.sqlite import insert
            else:
                from sqlalchemy.dialects.postgresql import insert

            upsert_stmt = insert(integrations).values(integration_dict)
            upsert_stmt = upsert_stmt.on_conflict_do_update(
                index_elements=[integrations.c.id],
                set_={
                    "enc_settings": upsert_stmt.excluded.enc_settings,
                    "description": upsert_stmt.excluded.description,
                    "version": upsert_stmt.excluded.version,
                    "updated_at": upsert_stmt.excluded.updated_at,
                },
            )

            try:
                await conn.execute(upsert_stmt)
            except IntegrityError as exc:
                raise PlatformHTTPError(
                    error_code=ErrorCode.UNEXPECTED,
                    message="Unexpected database integrity error",
                    data={
                        "error": str(exc),
                    },
                ) from exc

        # Auto-assign global scope for observability integrations without scopes
        if integration.kind == "observability":
            existing_scopes = await self.list_integration_scopes(integration.id)
            if not existing_scopes:
                await self.set_integration_scope(
                    integration_id=integration.id,
                    scope="global",
                    agent_id=None,
                )

    def _row_to_integration(self, row: RowMapping) -> Integration:
        row_dict = dict(row)
        settings_dict = self._decrypt_config(row_dict["enc_settings"])
        return Integration.model_validate(
            {
                "id": str(row_dict["id"]),
                "kind": row_dict["kind"],
                "description": row_dict.get("description"),
                "version": row_dict.get("version"),
                "settings": settings_dict,
                "created_at": row_dict["created_at"],
                "updated_at": row_dict["updated_at"],
            }
        )

    async def get_integration(self, integration_id: str) -> Integration:
        integrations = self._get_table("integration")

        async with self._read_connection() as conn:
            result = await conn.execute(sa.select(integrations).where(integrations.c.id == integration_id))
            row = result.mappings().fetchone()

        if row is None:
            raise IntegrationNotFoundError(integration_id, by="id")

        return self._row_to_integration(row)

    async def get_integration_by_kind(self, kind: str) -> Integration:
        """Get an integration by its kind."""
        integrations = self._get_table("integration")

        async with self._read_connection() as conn:
            result = await conn.execute(sa.select(integrations).where(integrations.c.kind == kind))
            row = result.mappings().fetchone()

            if row is None:
                raise IntegrationNotFoundError(kind, by="kind")

        return self._row_to_integration(row)

    async def delete_integration_by_id(self, integration_id: str) -> None:
        integrations = self._get_table("integration")

        async with self._write_connection() as conn:
            result = await conn.execute(sa.delete(integrations).where(integrations.c.id == integration_id))
            if result.rowcount == 0:
                raise IntegrationNotFoundError(integration_id, by="id")

    async def delete_integration(self, kind: str) -> None:
        """Delete an integration by its kind."""
        integrations = self._get_table("integration")

        async with self._write_connection() as conn:
            result = await conn.execute(sa.delete(integrations).where(integrations.c.kind == kind))
            if result.rowcount == 0:
                raise IntegrationNotFoundError(kind, by="kind")

    async def list_integrations(self, *, kind: str | None = None) -> list[Integration]:
        """List integrations optionally filtered by kind."""
        integrations = self._get_table("integration")

        query = sa.select(integrations)
        if kind is not None:
            query = query.where(integrations.c.kind == kind)

        async with self._read_connection() as conn:
            result = await conn.execute(query)
            rows = result.mappings().fetchall()

        integration_list = []
        for row in rows:
            integration_list.append(self._row_to_integration(row))

        return integration_list

    async def list_enabled_observability_integrations(self) -> list[ObservabilityIntegration]:
        """List all enabled observability integrations.

        Returns:
            List of ObservabilityIntegration instances that are enabled.
        """
        from agent_platform.core.integrations.observability.integration import (
            ObservabilityIntegration,
        )
        from agent_platform.core.integrations.settings.observability import (
            ObservabilityIntegrationSettings,
        )

        integrations = await self.list_integrations(kind="observability")
        enabled_obs_integrations = []
        for i in integrations:
            # isinstance check to filter only enabled observability integrations
            if isinstance(i.settings, ObservabilityIntegrationSettings) and i.settings.is_enabled:
                # Convert Integration to ObservabilityIntegration using model_validate
                obs_integration = ObservabilityIntegration.model_validate(i.model_dump())
                enabled_obs_integrations.append(obs_integration)
        return enabled_obs_integrations

    # -------------------------------------------------------------------------
    # Methods for Integration Scopes
    # -------------------------------------------------------------------------
    def _row_to_integration_scope(self, row: RowMapping) -> IntegrationScope:
        """Convert a database row to an IntegrationScope."""
        return IntegrationScope.model_validate(
            {
                "integration_id": str(row["integration_id"]),
                "agent_id": str(row["agent_id"]) if row.get("agent_id") else None,
                "scope": row["scope"],
                "created_at": row["created_at"],
            }
        )

    async def set_integration_scope(self, integration_id: str, scope: str, agent_id: str | None) -> IntegrationScope:
        """Assign an integration to a scope (global or agent-specific).

        Args:
            integration_id: ID of the integration to assign
            scope: Scope type ('global' or 'agent')
            agent_id: Agent ID if scope='agent', None if scope='global'

        Returns:
            Created IntegrationScope
        """

        # Validate scope value
        if scope not in ("global", "agent"):
            raise InvalidScopeError(f"Invalid scope: {scope}. Must be 'global' or 'agent'")

        # Validate scope-agent_id relationship
        if scope == "global" and agent_id is not None:
            raise InvalidScopeError("global scope must have agent_id=None")
        if scope == "agent" and agent_id is None:
            raise InvalidScopeError("agent scope must have agent_id set")

        integration_scopes = self._get_table("integration_scopes")

        scope_data = {
            "integration_id": integration_id,
            "scope": scope,
            "agent_id": agent_id,
        }

        async with self._write_connection() as conn:
            # Import appropriate insert based on dialect
            if self._sa_engine.dialect.name == "sqlite":
                from sqlalchemy.dialects.sqlite import insert
            else:
                from sqlalchemy.dialects.postgresql import insert

            # Use ON CONFLICT DO NOTHING (database automatically uses the unique indexes)
            stmt = insert(integration_scopes).values(scope_data)
            stmt = stmt.on_conflict_do_nothing()
            stmt = stmt.returning(integration_scopes)

            result = await conn.execute(stmt)
            row = result.mappings().fetchone()

        # If ON CONFLICT occurred, row is None - fetch existing
        if row is None:
            async with self._read_connection() as conn:
                where_clause = sa.and_(
                    integration_scopes.c.integration_id == integration_id,
                    (
                        integration_scopes.c.agent_id == agent_id
                        if agent_id is not None
                        else integration_scopes.c.agent_id.is_(None)
                    ),
                )
                result = await conn.execute(sa.select(integration_scopes).where(where_clause))
                existing_row = result.mappings().fetchone()
                # we are positive that the row exists, as we're in the ON CONFLICT DO NOTHING clause
                assert existing_row is not None
                return self._row_to_integration_scope(existing_row)
        else:
            return self._row_to_integration_scope(row)

    async def delete_integration_scope(self, integration_id: str, scope: str, agent_id: str | None) -> None:
        """Delete a scope assignment.

        Args:
            integration_id: ID of the integration
            scope: Scope type ('global' or 'agent')
            agent_id: Agent ID (or None for global scope)
        """
        integration_scopes = self._get_table("integration_scopes")

        async with self._write_connection() as conn:
            where_clause = sa.and_(
                integration_scopes.c.integration_id == integration_id,
                integration_scopes.c.scope == scope,
                (
                    integration_scopes.c.agent_id == agent_id
                    if agent_id is not None
                    else integration_scopes.c.agent_id.is_(None)
                ),
            )

            result = await conn.execute(sa.delete(integration_scopes).where(where_clause))
            if result.rowcount == 0:
                scope_desc = f"integration={integration_id}, scope={scope}, agent={agent_id or 'global'}"
                raise IntegrationScopeNotFoundError(scope_desc)

    async def list_integration_scopes(self, integration_id: str) -> list[IntegrationScope]:
        """List all scope assignments for an integration.

        Args:
            integration_id: ID of the integration

        Returns:
            List of IntegrationScope objects
        """
        integration_scopes = self._get_table("integration_scopes")

        async with self._read_connection() as conn:
            stmt = sa.select(integration_scopes).where(integration_scopes.c.integration_id == integration_id)
            result = await conn.execute(stmt)
            rows = result.mappings().fetchall()

        return [self._row_to_integration_scope(row) for row in rows]

    async def get_observability_integrations_for_agent(self, agent_id: str) -> list[Integration]:
        """Get all integrations for an agent (global + agent-specific), additive.

        This returns ALL integrations that apply to the agent:
        - All integrations with scope='global'
        - All integrations with scope='agent' where agent_id matches

        Args:
            agent_id: ID of the agent

        Returns:
            List of all applicable Integration objects
        """
        integrations = self._get_table("integration")
        integration_scopes = self._get_table("integration_scopes")

        # Note: We had to use a UNION ALL of two queries,
        # rather than a single query with an OR clause,
        # to avoid SQLite query planner issues with partial indexes.
        # See discussion: https://github.com/Sema4AI/agent-platform/pull/1722#discussion_r2557086094

        # Query 1: Get integrations with global scope
        global_query = (
            sa.select(integrations)
            .select_from(
                integrations.join(integration_scopes, integrations.c.id == integration_scopes.c.integration_id)
            )
            .where(
                integrations.c.kind == "observability",
                integration_scopes.c.scope == "global",
                integration_scopes.c.agent_id.is_(None),
            )
        )

        # Query 2: Get integrations with agent-specific scope
        agent_query = (
            sa.select(integrations)
            .select_from(
                integrations.join(integration_scopes, integrations.c.id == integration_scopes.c.integration_id)
            )
            .where(
                integrations.c.kind == "observability",
                integration_scopes.c.scope == "agent",
                integration_scopes.c.agent_id == agent_id,
            )
        )

        # Combine with UNION ALL
        query = sa.union_all(global_query, agent_query)

        async with self._read_connection() as conn:
            result = await conn.execute(query)
            rows = result.mappings().fetchall()

        return [self._row_to_integration(row) for row in rows]

    # Methods for listing semantic data models with associations
    # -------------------------------------------------------------------------
    class SemanticDataModelInfo(TypedDict):
        semantic_data_model: SemanticDataModel
        semantic_data_model_id: str
        agent_ids: set[str]
        thread_ids: set[str]
        updated_at: str

    async def list_semantic_data_models(
        self, agent_id: str | None = None, thread_id: str | None = None
    ) -> list[SemanticDataModelInfo]:
        """List semantic data models."""

        semantic_data_models = self._get_table("semantic_data_model")
        agent_semantic_data_models = self._get_table("agent_semantic_data_models")
        thread_semantic_data_models = self._get_table("thread_semantic_data_models")

        async with self._read_connection() as conn:
            # Build the base query with OUTER JOINs to get all associations
            query = sa.select(
                semantic_data_models,
                agent_semantic_data_models.c.agent_id,
                thread_semantic_data_models.c.thread_id,
            ).select_from(
                semantic_data_models.outerjoin(
                    agent_semantic_data_models,
                    semantic_data_models.c.id == agent_semantic_data_models.c.semantic_data_model_id,
                ).outerjoin(
                    thread_semantic_data_models,
                    semantic_data_models.c.id == thread_semantic_data_models.c.semantic_data_model_id,
                )
            )

            # Apply filters based on agent_id and/or thread_id
            if agent_id is not None and thread_id is not None:
                # Both agent_id and thread_id specified - find models associated with either
                query = query.where(
                    sa.or_(
                        agent_semantic_data_models.c.agent_id == agent_id,
                        thread_semantic_data_models.c.thread_id == thread_id,
                    )
                )
            elif agent_id is not None:
                # Filter by agent_id
                query = query.where(agent_semantic_data_models.c.agent_id == agent_id)
            elif thread_id is not None:
                # Filter by thread_id
                query = query.where(thread_semantic_data_models.c.thread_id == thread_id)

            result = await conn.execute(query)
            rows = result.mappings().fetchall()

            # Group results by semantic data model ID and collect associations
            models_by_id = {}

            for row in rows:
                model_id = str(row["id"])

                if model_id not in models_by_id:
                    # PostgreSQL: SQLAlchemy returns JSONB as dict (no parsing needed)
                    # SQLite: SQLAlchemy returns TEXT as string (needs json.loads)
                    semantic_model = row["semantic_model"]
                    # Parse if string (SQLite normal, or PostgreSQL legacy double-serialized)
                    if isinstance(semantic_model, str):
                        semantic_model = json.loads(semantic_model)

                    updated_at = row["updated_at"]
                    if isinstance(updated_at, datetime):
                        updated_at = updated_at.isoformat()

                    models_by_id[model_id] = {
                        "semantic_data_model": semantic_model,
                        "semantic_data_model_id": model_id,
                        "agent_ids": set(),
                        "thread_ids": set(),
                        "updated_at": updated_at,
                    }

                # Collect agent_id if present
                if row["agent_id"] is not None:
                    models_by_id[model_id]["agent_ids"].add(str(row["agent_id"]))

                # Collect thread_id if present
                if row["thread_id"] is not None:
                    models_by_id[model_id]["thread_ids"].add(str(row["thread_id"]))

            # Convert to list and return
            results = list(models_by_id.values())
            return results

    # -------------------------------------------------------------------------
    # Methods for Data Frames Cache
    # -------------------------------------------------------------------------

    @dataclasses.dataclass(frozen=True)
    class CacheValue:
        cache_data: bytes
        time_to_compute_data_in_seconds: float
        cache_size_in_bytes: int

    async def get_cache_entry(self, cache_key: str) -> CacheValue | None:
        """Get a cache entry by key."""
        cache_table = self._get_table("data_cache")

        stmt = sa.select(
            cache_table.c.cache_data,
            cache_table.c.time_to_compute_data_in_seconds,
            cache_table.c.cache_size_in_bytes,
        ).where(cache_table.c.cache_key == cache_key)

        async with self._read_connection() as conn:
            result = await conn.execute(stmt)
            row = result.mappings().first()

            if row is None:
                return None

        await self._update_last_accessed_at(cache_table, cache_key)

        return self.CacheValue(
            cache_data=row["cache_data"],
            time_to_compute_data_in_seconds=float(row["time_to_compute_data_in_seconds"]),
            cache_size_in_bytes=int(row["cache_size_in_bytes"]),
        )

    async def _update_last_accessed_at(self, cache_table, cache_key: list[str] | str):
        try:
            async with self._write_connection() as conn:
                # Update last_accessed_at
                if isinstance(cache_key, str):
                    update_stmt = (
                        sa.update(cache_table)
                        .where(cache_table.c.cache_key == cache_key)
                        .values(last_accessed_at=datetime.now(UTC))
                    )
                else:
                    update_stmt = (
                        sa.update(cache_table)
                        .where(cache_table.c.cache_key.in_(cache_key))
                        .values(last_accessed_at=datetime.now(UTC))
                    )
                await conn.execute(update_stmt)
        except Exception:
            logger.error(f"Error updating last_accessed_at for cache key {cache_key}", exc_info=True)

    async def get_cache_entries(self, cache_keys: list[str]) -> dict[str, CacheValue]:
        """Get cache entries by keys."""
        cache_table = self._get_table("data_cache")

        if not cache_keys:
            return {}

        stmt = sa.select(
            cache_table.c.cache_key,
            cache_table.c.cache_data,
            cache_table.c.time_to_compute_data_in_seconds,
            cache_table.c.cache_size_in_bytes,
        ).where(cache_table.c.cache_key.in_(cache_keys))

        async with self._read_connection() as conn:
            result = await conn.execute(stmt)
            rows = result.mappings().fetchall()

        # Build result dictionary
        cache_entries = {}
        for row in rows:
            cache_key = row["cache_key"]
            cache_entries[cache_key] = self.CacheValue(
                cache_data=row["cache_data"],
                time_to_compute_data_in_seconds=float(row["time_to_compute_data_in_seconds"]),
                cache_size_in_bytes=int(row["cache_size_in_bytes"]),
            )

        await self._update_last_accessed_at(cache_table, list(cache_entries.keys()))

        return cache_entries

    async def set_cache_entry(
        self,
        cache_key: str,
        cache_data: bytes,
        time_to_compute_data_in_seconds: float,
        *,
        last_accessed_at: datetime | None = None,
    ) -> None:
        """Set a cache entry."""
        cache_table = self._get_table("data_cache")

        cache_size_in_bytes = len(cache_data)

        # Use dialect-specific insert to support upsert (update on conflict)
        if self._sa_engine.dialect.name == "sqlite":
            from sqlalchemy.dialects.sqlite import insert
        else:
            from sqlalchemy.dialects.postgresql import insert

        stmt = insert(cache_table).values(
            cache_key=cache_key,
            cache_data=cache_data,
            last_accessed_at=(last_accessed_at if last_accessed_at is not None else datetime.now(UTC)),
            time_to_compute_data_in_seconds=time_to_compute_data_in_seconds,
            cache_size_in_bytes=cache_size_in_bytes,
        )

        # On conflict of primary key (cache_key), update the stored values
        stmt = stmt.on_conflict_do_update(
            index_elements=[cache_table.c.cache_key],
            set_={
                "cache_data": stmt.excluded.cache_data,
                "last_accessed_at": stmt.excluded.last_accessed_at,
                "time_to_compute_data_in_seconds": stmt.excluded.time_to_compute_data_in_seconds,
                "cache_size_in_bytes": stmt.excluded.cache_size_in_bytes,
            },
        )

        async with self._write_connection() as conn:
            await conn.execute(stmt)

    async def evict_old_cache_entries_by_size(self, max_cache_size_bytes: int = 100 * 1024 * 1024) -> None:
        """Evict old cache entries using LRU strategy."""
        cache_table = self._get_table("data_cache")

        # Compute cumulative sum ordered by last_accessed_at descending (oldest first)
        running_sum = sa.func.sum(cache_table.c.cache_size_in_bytes).over(
            order_by=cache_table.c.last_accessed_at.desc()
        )

        # Subquery that includes running sum for each row
        subq = (
            sa.select(
                cache_table.c.cache_key,
                cache_table.c.cache_size_in_bytes,
                cache_table.c.last_accessed_at,
                running_sum.label("running_sum"),
            )
            .order_by(cache_table.c.last_accessed_at.desc())
            .subquery()
        )

        # Delete the rows that exceed the max cache size
        stmt = sa.select(subq).where(subq.c.running_sum > max_cache_size_bytes)
        async with self._read_connection() as conn:
            result = await conn.execute(stmt)
            entries = result.mappings().fetchall()
            keys_to_delete = [entry["cache_key"] for entry in entries]

        if keys_to_delete:
            async with self._write_connection() as conn:
                delete_stmt = cache_table.delete().where(cache_table.c.cache_key.in_(keys_to_delete))
                result = await conn.execute(delete_stmt)
                if result.rowcount > 0:
                    logger.info(f"Evicted {result.rowcount} cache entries")

    async def evict_old_cache_entries_by_date(self, max_age_days: int = 30) -> None:
        """Evict old cache entries by date."""
        cache_table = self._get_table("data_cache")

        # Calculate the cutoff date
        cutoff_date = datetime.now(UTC) - timedelta(days=max_age_days)

        # Delete entries older than the cutoff date
        if self._sa_engine.dialect.name == "sqlite":
            delete_stmt = cache_table.delete().where(cache_table.c.last_accessed_at < cutoff_date.isoformat())
        else:
            delete_stmt = cache_table.delete().where(cache_table.c.last_accessed_at < cutoff_date)

        async with self._write_connection() as conn:
            result = await conn.execute(delete_stmt)
            if result.rowcount > 0:
                logger.info(f"Evicted {result.rowcount} cache entries older than {max_age_days} days")

    async def list_cached_entries(self) -> dict[str, CacheValue]:
        cache_table = self._get_table("data_cache")
        stmt = sa.select(
            cache_table.c.cache_key,
            cache_table.c.cache_data,
            cache_table.c.time_to_compute_data_in_seconds,
            cache_table.c.cache_size_in_bytes,
        )

        async with self._read_connection() as conn:
            result = await conn.execute(stmt)
            rows = result.mappings().fetchall()
            return {
                row["cache_key"]: self.CacheValue(
                    cache_data=row["cache_data"],
                    time_to_compute_data_in_seconds=float(row["time_to_compute_data_in_seconds"]),
                    cache_size_in_bytes=int(row["cache_size_in_bytes"]),
                )
                for row in rows
            }

    # -------------------------------------------------------------------------
    # Methods for OAuth Token Storage
    # -------------------------------------------------------------------------

    async def _load_mcp_oauth_token_from_row(self, row: RowMapping, *, decrypt: bool = False) -> "OAuthToken":
        from mcp.shared.auth import OAuthToken

        # Decrypt tokens if requested
        if decrypt:
            access_token = self._secret_manager.fetch(row["access_token_enc"])
            refresh_token = self._secret_manager.fetch(row["refresh_token_enc"]) if row["refresh_token_enc"] else None
        else:
            access_token = row["access_token_enc"]
            refresh_token = row["refresh_token_enc"]

        # Calculate updated expires_in based on current time
        expires_in = row["expires_in"]
        if expires_in is not None:
            # Get the updated_at timestamp (when token was last saved)
            if self._sa_engine.dialect.name == "sqlite":
                updated_at_str = row["updated_at"]
                updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
            else:
                updated_at = row["updated_at"]

            # Calculate elapsed time since token was saved
            now = datetime.now(UTC)
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=UTC)
            elapsed_seconds = int((now - updated_at).total_seconds())

            # Recalculate expires_in based on current time
            expires_in = max(0, expires_in - elapsed_seconds)

        return OAuthToken(
            access_token=access_token,
            token_type=row["token_type"] or "Bearer",
            expires_in=expires_in,
            scope=row["scope"],
            refresh_token=refresh_token,
        )

    async def get_mcp_server_to_oauth_token(self, user_id: str, *, decrypt: bool = False) -> dict[str, "OAuthToken"]:
        """
        Get a dictionary of MCP server URLs to OAuth tokens for a user.
        Should be used for getting the status of all MCP servers that the user has access to.

        Args:
            user_id: The ID of the user

        Returns:
            A dictionary of MCP server URLs to OAuth tokens
        """
        from mcp.shared.auth import OAuthToken

        token_table = self._get_table("oauth_token")

        stmt = sa.select(token_table).where(token_table.c.user_id == user_id)

        async with self._read_connection() as conn:
            result = await conn.execute(stmt)
            rows = result.mappings().all()

        result_dict: dict[str, OAuthToken] = {}

        for row in rows:
            token = await self._load_mcp_oauth_token_from_row(row=row, decrypt=decrypt)

            mcp_url = str(row["mcp_url"])
            result_dict[mcp_url] = token

        return result_dict

    async def get_mcp_oauth_token(self, user_id: str, mcp_url: str, *, decrypt: bool = False) -> "OAuthToken | None":
        """Get OAuth token for a user and MCP server. May return None if no token is found."""

        token_table = self._get_table("oauth_token")

        stmt = sa.select(token_table).where((token_table.c.user_id == user_id) & (token_table.c.mcp_url == mcp_url))

        async with self._read_connection() as conn:
            result = await conn.execute(stmt)
            row = result.mappings().first()

            if row is None:
                return None
            return await self._load_mcp_oauth_token_from_row(row=row, decrypt=decrypt)

    async def set_mcp_oauth_token(
        self,
        user_id: str,
        mcp_url: str,
        token: "OAuthToken",
    ) -> None:
        """Set OAuth token for a user and MCP server."""
        token_table = self._get_table("oauth_token")

        # Encrypt tokens
        access_token_enc = self._secret_manager.store(token.access_token)
        refresh_token_enc = self._secret_manager.store(token.refresh_token) if token.refresh_token else None
        if token.expires_in is not None:
            expires_at = datetime.now(UTC) + timedelta(seconds=token.expires_in)
        else:
            expires_at = datetime.now(UTC) + timedelta(seconds=3600)  # 1 hour

        # Prepare values
        values = {
            "user_id": user_id,
            "mcp_url": mcp_url,
            "access_token_enc": access_token_enc,
            "token_type": token.token_type or "Bearer",
            "expires_in": token.expires_in,
            "scope": token.scope,
            "refresh_token_enc": refresh_token_enc,
            "updated_at": datetime.now(UTC),
            "expires_at": expires_at,
        }

        # Use dialect-specific insert for upsert
        if self._sa_engine.dialect.name == "sqlite":
            from sqlalchemy.dialects.sqlite import insert
        else:
            from sqlalchemy.dialects.postgresql import insert

        stmt = insert(token_table).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "mcp_url"],
            set_={
                "access_token_enc": stmt.excluded.access_token_enc,
                "token_type": stmt.excluded.token_type,
                "expires_in": stmt.excluded.expires_in,
                "scope": stmt.excluded.scope,
                "refresh_token_enc": stmt.excluded.refresh_token_enc,
                "updated_at": stmt.excluded.updated_at,
            },
        )

        async with self._write_connection() as conn:
            await conn.execute(stmt)

    async def delete_mcp_oauth_token(self, user_id: str, mcp_url: str) -> None:
        """Delete OAuth token for a user and MCP server."""
        token_table = self._get_table("oauth_token")

        stmt = token_table.delete().where((token_table.c.user_id == user_id) & (token_table.c.mcp_url == mcp_url))

        async with self._write_connection() as conn:
            await conn.execute(stmt)

    # -------------------------------------------------------------------------
    # Methods for OAuth Client Information Storage
    # -------------------------------------------------------------------------
    async def get_mcp_oauth_client_info(
        self, user_id: str, mcp_url: str, *, decrypt: bool = False
    ) -> "OAuthClientInformationFull | None":
        """Get OAuth client information for a user and MCP server."""
        from mcp.shared.auth import OAuthClientInformationFull

        client_table = self._get_table("oauth_client_info")

        stmt = sa.select(client_table).where((client_table.c.user_id == user_id) & (client_table.c.mcp_url == mcp_url))

        async with self._read_connection() as conn:
            result = await conn.execute(stmt)
            row = result.mappings().first()

            if row is None:
                return None

        if decrypt:
            # Decrypt client_id and client_secret
            client_id = self._secret_manager.fetch(row["client_id_enc"])
            client_secret = self._secret_manager.fetch(row["client_secret_enc"]) if row["client_secret_enc"] else None
        else:
            client_id = row["client_id_enc"]
            client_secret = row["client_secret_enc"]

        # Parse metadata JSON
        if self._sa_engine.dialect.name == "sqlite":
            metadata_dict = json.loads(row["metadata_json"])
        else:
            metadata_dict = row["metadata_json"]

        # Reconstruct OAuthClientInformationFull
        return OAuthClientInformationFull(
            client_id=client_id,
            client_secret=client_secret,
            client_id_issued_at=row["client_id_issued_at"],
            client_secret_expires_at=row["client_secret_expires_at"],
            **metadata_dict,
        )

    async def set_mcp_oauth_client_info(
        self,
        user_id: str,
        mcp_url: str,
        client_info: "OAuthClientInformationFull",
    ) -> None:
        """Set OAuth client information for a user and MCP server."""
        from agent_platform.server.data_frames.data_node import convert_to_valid_json_types

        client_table = self._get_table("oauth_client_info")

        # Encrypt client_id and client_secret
        client_id_enc = self._secret_manager.store(client_info.client_id)
        client_secret_enc = self._secret_manager.store(client_info.client_secret) if client_info.client_secret else None

        # Extract metadata (everything except client_id, client_secret, client_id_issued_at
        # and client_secret_expires_at)
        metadata_dict = client_info.model_dump(
            exclude={
                "client_id",
                "client_secret",
                "client_id_issued_at",
                "client_secret_expires_at",
            }
        )

        # Convert to python basic types
        if metadata_dict:
            metadata_dict = convert_to_valid_json_types(metadata_dict)

        # Prepare values
        values = {
            "user_id": user_id,
            "mcp_url": mcp_url,
            "client_id_enc": client_id_enc,
            "client_secret_enc": client_secret_enc,
            "client_id_issued_at": client_info.client_id_issued_at,
            "client_secret_expires_at": client_info.client_secret_expires_at,
            "updated_at": datetime.now(UTC),
            "expires_at": (
                datetime.fromtimestamp(timestamp=client_info.client_secret_expires_at, tz=UTC)
                if client_info.client_secret_expires_at
                else None
            ),
        }

        # Handle JSON serialization for SQLite
        if self._sa_engine.dialect.name == "sqlite":
            values["metadata_json"] = json.dumps(metadata_dict)
        else:
            values["metadata_json"] = metadata_dict

        # Use dialect-specific insert for upsert
        if self._sa_engine.dialect.name == "sqlite":
            from sqlalchemy.dialects.sqlite import insert
        else:
            from sqlalchemy.dialects.postgresql import insert

        stmt = insert(client_table).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "mcp_url"],
            set_={
                "client_id_enc": stmt.excluded.client_id_enc,
                "client_secret_enc": stmt.excluded.client_secret_enc,
                "client_id_issued_at": stmt.excluded.client_id_issued_at,
                "client_secret_expires_at": stmt.excluded.client_secret_expires_at,
                "metadata_json": stmt.excluded.metadata_json,
                "updated_at": stmt.excluded.updated_at,
            },
        )

        async with self._write_connection() as conn:
            await conn.execute(stmt)

    async def delete_mcp_oauth_client_info(self, user_id: str, mcp_url: str) -> None:
        """Delete OAuth client information for a user and MCP server."""
        client_table = self._get_table("oauth_client_info")

        stmt = client_table.delete().where((client_table.c.user_id == user_id) & (client_table.c.mcp_url == mcp_url))

        async with self._write_connection() as conn:
            await conn.execute(stmt)

    # -------------------------------------------------------------------------
    # Methods for OAuth Callback Result Storage
    # -------------------------------------------------------------------------
    async def get_mcp_oauth_callback_result(self, callback_id: str) -> "OAuthCallbackResult | None":
        """Get OAuth callback result by callback_id."""
        from agent_platform.server.oauth.oauth_provider import OAuthCallbackResult

        callback_table = self._get_table("oauth_callback_result")

        stmt = sa.select(callback_table).where(callback_table.c.callback_id == callback_id)

        async with self._read_connection() as conn:
            result = await conn.execute(stmt)
            row = result.mappings().first()

            if row is None:
                return None

        # Reconstruct OAuthCallbackResult
        error = None
        if row["error_message"]:
            error = Exception(row["error_message"])

        return OAuthCallbackResult(
            code=row["code"],
            state=row["state"],
            error=error,
        )

    async def set_mcp_oauth_callback_result(
        self,
        callback_id: str,
        code: str | None = None,
        state: str | None = None,
        error: Exception | None = None,
    ) -> None:
        """Set OAuth callback result."""
        callback_table = self._get_table("oauth_callback_result")

        values = {
            "callback_id": callback_id,
            "code": code,
            "state": state,
            "error_message": str(error) if error else None,
        }

        # Use dialect-specific insert for upsert
        if self._sa_engine.dialect.name == "sqlite":
            from sqlalchemy.dialects.sqlite import insert

            stmt = insert(callback_table).values(**values)
            stmt = stmt.on_conflict_do_update(
                index_elements=["callback_id"],
                set_={
                    "code": stmt.excluded.code,
                    "state": stmt.excluded.state,
                    "error_message": stmt.excluded.error_message,
                },
            )
        else:
            from sqlalchemy.dialects.postgresql import insert

            stmt = insert(callback_table).values(**values)
            stmt = stmt.on_conflict_do_update(
                index_elements=["callback_id"],
                set_={
                    "code": stmt.excluded.code,
                    "state": stmt.excluded.state,
                    "error_message": stmt.excluded.error_message,
                },
            )

        async with self._write_connection() as conn:
            await conn.execute(stmt)
