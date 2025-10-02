import typing
from pathlib import Path

if typing.TYPE_CHECKING:
    from agent_platform.core.agent import Agent
    from agent_platform.core.data_connections.data_connections import DataConnection
    from agent_platform.core.data_frames import (
        DataFrameSource,
        PlatformDataFrame,
    )
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
            source_type="data_frame",
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

    async def obtain_sample_agent(self, agent_name: str = "Test Agent") -> "Agent":
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

    async def obtain_sample_data_frame(self, name: str = "test_data_frame") -> "PlatformDataFrame":
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
    ) -> "DataConnection":
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

    async def obtain_sample_semantic_data_model(self, name: str = "test_model") -> str:
        """Create a sample semantic data model for testing."""

        # Create a simple semantic data model
        semantic_model = {
            "name": name,
            "description": f"Test semantic data model: {name}",
            "entities": [
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
