from __future__ import annotations

import typing
from pathlib import Path

if typing.TYPE_CHECKING:
    from agent_platform.core.agent import Agent
    from agent_platform.core.context import AgentServerContext
    from agent_platform.core.data_connections.data_connections import DataConnection
    from agent_platform.core.data_frames import (
        DataFrameSource,
        PlatformDataFrame,
    )
    from agent_platform.core.data_frames.semantic_data_model_types import SemanticDataModel
    from agent_platform.core.files import UploadedFile
    from agent_platform.core.thread import Thread
    from agent_platform.core.work_items.work_item import WorkItem
    from agent_platform.server.auth.handlers import AuthedUser
    from agent_platform.server.kernel.kernel import AgentServerKernel
    from agent_platform.server.storage.base import BaseStorage
    from agent_platform.server.storage.postgres import PostgresStorage
    from agent_platform.server.storage.sqlite import SQLiteStorage


class SampleModelCreator:
    """
    Helper class to create sample models for testing.

    The `obtain_xxx` methods create the instances and automatically adds those to the
    storage.
    """

    def __init__(self, storage: PostgresStorage | SQLiteStorage | BaseStorage, tmpdir: Path):
        self.storage = storage
        self.tmpdir = tmpdir

        self.sample_agent = None
        self.sample_thread = None
        self.sample_file: UploadedFile | None = None
        self.sample_data_frame = None

    async def setup(self) -> None:
        await self.storage.get_or_create_user(sub="tenant:testing:system:system_user")

    async def obtain_sample_data_frame_source(self) -> DataFrameSource:
        """Create a sample DataFrameSource for testing."""
        from agent_platform.core.data_frames.data_frames import DataFrameSource

        return DataFrameSource(
            source_type="data_frame",
            source_id="external-postgres-connection",
        )

    async def obtain_sample_file(
        self,
        file_content: bytes = b"test content",
        file_name: str = "test.txt",
        mime_type: str = "text/plain",
        owner: Agent | Thread | WorkItem | None = None,
    ) -> UploadedFile:
        """Create a sample file for testing."""
        from hashlib import md5
        from uuid import uuid4

        from fastapi import UploadFile

        from sema4ai.common import uris

        if self.sample_file is not None:
            return self.sample_file

        file_path = Path(self.tmpdir) / file_name
        file_path.write_bytes(file_content)
        with file_path.open("rb") as file_stream:
            sample_file = UploadFile(filename=file_name, file=file_stream)

        file_id = str(uuid4())
        orig_path = uris.from_fs_path(str(file_path))
        assert sample_file.filename is not None
        file_hash = md5(sample_file.filename.encode()).hexdigest()

        # Upload the file with one ID
        self.sample_file = await self.storage.put_file_owner(
            file_id=file_id,
            owner=owner or await self.obtain_sample_thread(),
            user_id=await self.get_user_id(),
            file_path=orig_path,
            file_ref=sample_file.filename,
            file_hash=file_hash,
            file_size_raw=len(file_content),
            mime_type=mime_type,
            embedded=False,
            embedding_status=None,
            file_path_expiration=None,
        )
        return self.sample_file

    async def get_user_id(self) -> str:
        return await self.storage.get_system_user_id()

    async def get_authed_user(self) -> AuthedUser:
        from agent_platform.core.user import User

        return User(user_id=await self.get_user_id(), sub="tenant:testing:user:test_user")

    async def obtain_sample_agent(self, agent_name: str = "Test Agent") -> Agent:
        from datetime import UTC, datetime
        from uuid import uuid4

        from agent_platform.core.actions.action_package import ActionPackage
        from agent_platform.core.agent.agent import Agent
        from agent_platform.core.agent.agent_architecture import AgentArchitecture
        from agent_platform.core.runbook.runbook import Runbook
        from agent_platform.core.utils.secret_str import SecretString

        if self.sample_agent is not None:
            return self.sample_agent

        sample_user_id = await self.get_user_id()
        self.sample_agent = Agent(
            user_id=sample_user_id,
            agent_id=str(uuid4()),
            name=agent_name,
            description="Test Description",
            runbook_structured=Runbook(
                raw_text="# Objective\nYou are a helpful assistant.",
                content=[],
            ),
            version="1.0.0",
            updated_at=datetime.now(UTC),
            created_at=datetime.now(UTC),
            action_packages=[
                ActionPackage(
                    name="test-action-package",
                    organization="test-organization",
                    version="1.0.0",
                    url="https://api.test.com",
                    api_key=SecretString("test"),
                    allowed_actions=["action_1", "action_2"],
                ),
                ActionPackage(
                    name="test-action-package-2",
                    organization="test-organization-2",
                    version="1.0.0",
                    url="https://api.test-2.com",
                    api_key=SecretString("test-2"),
                    allowed_actions=[],
                ),
            ],
            agent_architecture=AgentArchitecture(
                name="agent-architecture-default-v2",
                version="1.0.0",
            ),
            question_groups=[],
            observability_configs=[],
            platform_configs=[],
            extra={"agent_extra": "some_extra_value"},
        )

        await self.storage.upsert_agent(sample_user_id, self.sample_agent)
        return self.sample_agent

    async def obtain_sample_thread(
        self,
    ) -> Thread:
        from datetime import UTC, datetime
        from uuid import uuid4

        from agent_platform.core.thread.thread import Thread

        sample_agent = await self.obtain_sample_agent()
        sample_user_id = await self.get_user_id()

        if self.sample_thread is not None:
            return self.sample_thread

        thread = Thread(
            thread_id=str(uuid4()),
            user_id=sample_user_id,
            agent_id=sample_agent.agent_id,
            name="Test Thread",
            messages=[],
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            metadata={"thread_metadata": "some_metadata"},
        )
        self.sample_thread = thread
        await self.storage.upsert_thread(sample_user_id, self.sample_thread)
        return self.sample_thread

    async def obtain_sample_data_frame(self, name: str = "test_data_frame") -> PlatformDataFrame:
        """Create a sample PlatformDataFrame for testing."""
        from datetime import UTC, datetime
        from uuid import uuid4

        from agent_platform.core.data_frames.data_frames import (
            DataFrameSource,
            ExtraDataFrameData,
            PlatformDataFrame,
        )

        sample_user_id = await self.get_user_id()

        sample_agent = await self.obtain_sample_agent()

        sample_thread = await self.obtain_sample_thread()

        sample_file = await self.obtain_sample_file()

        self.sample_data_frame = PlatformDataFrame(
            data_frame_id=str(uuid4()),
            user_id=sample_user_id,
            agent_id=sample_agent.agent_id,
            thread_id=sample_thread.thread_id,
            num_rows=100,
            num_columns=5,
            column_headers=["col1", "col2", "col3", "col4", "col5"],
            name=name,
            input_id_type="file",
            created_at=datetime.now(UTC),
            computation_input_sources={
                "source_1": DataFrameSource(
                    source_type="data_frame",
                    source_id="some-data-frame-id",
                ),
                "source_2": DataFrameSource(
                    source_type="data_frame",
                    source_id="external-postgres-connection-2",
                ),
            },
            file_id=sample_file.file_id,
            description="A test data frame for testing purposes",
            computation=None,
            parquet_contents=b"test_parquet_content",
            sheet_name="Sheet1",
            extra_data=typing.cast(ExtraDataFrameData, {"key": "value"}),
        )
        await self.storage.save_data_frame(self.sample_data_frame)
        return self.sample_data_frame

    async def obtain_sample_data_connection(
        self, name: str = "test_connection", db_file_path: Path | None = None
    ) -> DataConnection:
        """Create a sample DataConnection for testing."""
        from uuid import uuid4

        from agent_platform.core.data_connections.data_connections import DataConnection
        from agent_platform.core.payloads.data_connection import SQLiteDataConnectionConfiguration

        if db_file_path is None:
            db_file_dir = Path(self.tmpdir)
            # create a temp file for the db file (name must be unique)
            db_file_path = db_file_dir / f"sqlite_test_{uuid4()}.db"

        data_connection = DataConnection(
            id=str(uuid4()),
            name=name,
            description=f"Test data connection: {name}",
            engine="sqlite",
            configuration=SQLiteDataConnectionConfiguration(
                db_file=str(db_file_path),
            ),
            external_id=None,
            created_at=None,
            updated_at=None,
        )

        await self.storage.set_data_connection(data_connection)
        return data_connection

    async def obtain_sample_semantic_data_model(
        self, name: str = "test_model", semantic_model: SemanticDataModel | None = None
    ) -> str:
        """Create a sample semantic data model for testing."""

        if semantic_model is None:
            # Create a simple semantic data model
            semantic_model = {
                "name": name,
                "description": f"Test semantic data model: {name}",
                "tables": [
                    {
                        "name": "test_entity",
                        "description": "A test entity",
                        "base_table": {
                            "database": "test_db",
                            "schema": "test_schema",
                            "table": "test_table",
                        },
                    }
                ],
            }

        # Create the semantic data model in storage
        semantic_data_model_id = await self.storage.set_semantic_data_model(
            semantic_data_model_id=None,
            semantic_model=semantic_model,
            data_connection_ids=[],
            file_references=[],
        )

        return semantic_data_model_id

    async def create_agent_server_context(self) -> AgentServerContext:
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.trace import TracerProvider

        from agent_platform.core.context import (
            AgentServerContext,
            HttpContext,
            Request,
            Response,
            User,
            UserContext,
        )

        user_id = await self.get_user_id()

        ctx = AgentServerContext(
            http=HttpContext(request=Request(scope={"type": "http"}), response=Response()),
            user_context=UserContext(
                user=User(user_id=user_id, sub="tenant:test_tenant:user:test_user"),
                profile={},
            ),
            tracer_provider=TracerProvider(),
            meter_provider=MeterProvider(),
        )
        return ctx

    async def create_agent_server_kernel(self) -> AgentServerKernel:
        from uuid import uuid4

        from agent_platform.core.runs.run import Run
        from agent_platform.server.kernel.kernel import AgentServerKernel

        ctx = await self.create_agent_server_context()
        sample_agent = await self.obtain_sample_agent()
        sample_thread = await self.obtain_sample_thread()

        empty_run = Run(
            run_id=str(uuid4()),
            agent_id=sample_agent.agent_id,
            thread_id=sample_thread.thread_id,
        )
        kernel = AgentServerKernel(
            ctx=ctx,
            thread=sample_thread,
            agent=sample_agent,
            run=empty_run,
        )
        return kernel

    async def create_work_item(self) -> WorkItem:
        from uuid import uuid4

        from agent_platform.core.work_items.work_item import WorkItem

        work_item = WorkItem(
            work_item_id=str(uuid4()),
            user_id=await self.get_user_id(),
            created_by=await self.get_user_id(),
        )
        await self.storage.create_work_item(work_item)
        return work_item

    async def create_in_memory_data_frame(self, name: str, columns: list[str], rows: list[list]) -> PlatformDataFrame:
        from agent_platform.server.kernel.data_frames import create_data_frame_from_columns_and_rows

        data_frame = await create_data_frame_from_columns_and_rows(
            columns=columns,
            rows=rows,
            name=name,
            user_id=await self.get_user_id(),
            agent_id=(await self.obtain_sample_agent()).agent_id,
            thread_id=(await self.obtain_sample_thread()).thread_id,
            storage=self.storage,
        )
        return data_frame
