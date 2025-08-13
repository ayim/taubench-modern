import typing
from pathlib import Path

if typing.TYPE_CHECKING:
    from agent_platform.core.agent import Agent
    from agent_platform.core.data_frames import DataFrameSource, PlatformDataFrame
    from agent_platform.core.files import UploadedFile
    from agent_platform.core.thread import Thread
    from agent_platform.server.storage.postgres import PostgresStorage
    from agent_platform.server.storage.sqlite import SQLiteStorage


class SampleModelCreator:
    """
    Helper class to create sample models for testing.

    The `obtain_xxx` methods create the instances and automatically adds those to the
    storage.
    """

    def __init__(self, storage: "PostgresStorage | SQLiteStorage", tmpdir: Path):
        from agent_platform.core.files.files import UploadedFile

        self.storage = storage
        self.tmpdir = tmpdir

        self.sample_agent = None
        self.sample_thread = None
        self.sample_file: UploadedFile | None = None
        self.sample_data_frame = None

    async def setup(self) -> None:
        await self.storage.get_or_create_user(sub="tenant:testing:system:system_user")

    async def obtain_sample_data_frame_source(self) -> "DataFrameSource":
        """Create a sample DataFrameSource for testing."""
        from agent_platform.core.data_frames.data_frames import DataFrameSource

        return DataFrameSource(
            source_type="data_source",
            source_id="external-postgres-connection",
        )

    async def obtain_sample_file(self) -> "UploadedFile":
        """Create a sample file for testing."""
        from hashlib import md5
        from uuid import uuid4

        from fastapi import UploadFile

        if self.sample_file is not None:
            return self.sample_file

        file_content = b"test content"
        file_path = Path(self.tmpdir) / "test.txt"
        file_path.write_bytes(file_content)
        with file_path.open("rb") as file_stream:
            sample_file = UploadFile(filename="test.txt", file=file_stream)

        file_id = str(uuid4())
        orig_path = "path1"
        assert sample_file.filename is not None
        file_hash = md5(sample_file.filename.encode()).hexdigest()
        sample_thread = await self.obtain_sample_thread()

        # Upload the file with one ID
        self.sample_file = await self.storage.put_file_owner(
            file_id=file_id,
            owner=sample_thread,
            user_id=sample_thread.user_id,
            file_path=orig_path,
            file_ref=sample_file.filename,
            file_hash=file_hash,
            file_size_raw=0,
            mime_type="text/plain",
            embedded=False,
            embedding_status=None,
            file_path_expiration=None,
        )
        return self.sample_file

    async def get_user_id(self) -> str:
        return await self.storage.get_system_user_id()

    async def obtain_sample_agent(self) -> "Agent":
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
            name="Test Agent",
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
    ) -> "Thread":
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

    async def obtain_sample_data_frame(self) -> "PlatformDataFrame":
        """Create a sample PlatformDataFrame for testing."""
        from datetime import UTC, datetime
        from uuid import uuid4

        from agent_platform.core.data_frames.data_frames import DataFrameSource, PlatformDataFrame

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
            name="Test Data Frame",
            input_id_type="file",
            created_at=datetime.now(UTC),
            computation_input_sources={
                "source_1": DataFrameSource(
                    source_type="data_frame",
                    source_id="some-data-frame-id",
                ),
                "source_2": DataFrameSource(
                    source_type="data_source",
                    source_id="external-postgres-connection-2",
                ),
            },
            file_id=sample_file.file_id,
            description="A test data frame for testing purposes",
            computation=None,
            parquet_contents=b"test_parquet_content",
            sheet_name="Sheet1",
            extra_data={"key": "value"},
        )
        await self.storage.save_data_frame(self.sample_data_frame)
        return self.sample_data_frame
