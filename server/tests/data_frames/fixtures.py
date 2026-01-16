import typing

from structlog import get_logger

if typing.TYPE_CHECKING:
    from agent_platform.core.data_frames.data_frames import PlatformDataFrame
    from agent_platform.core.files.files import UploadedFile
    from agent_platform.server.storage.base import BaseStorage

logger = get_logger(__name__)


class UserStub:
    def __init__(self):
        from uuid import uuid4

        self.user_id = str(uuid4())


class ThreadStub:
    def __init__(self):
        from uuid import uuid4

        self.tid = self.thread_id = str(uuid4())
        self.agent_id = str(uuid4())
        self.user = UserStub()


class StorageStub:
    def __init__(self):
        from agent_platform.core.data_frames.data_frames import PlatformDataFrame

        self.thread = ThreadStub()
        self.data_frames: list[PlatformDataFrame] = []
        self._files: dict[str, UploadedFile] = {}

    async def list_semantic_data_models(
        self, agent_id: str | None = None, thread_id: str | None = None
    ) -> list["BaseStorage.SemanticDataModelInfo"]:
        return []

    async def get_data_connections(self, data_connection_ids: list[str]) -> list:
        """Mock method for getting data connections."""
        return []

    async def get_file_by_ref(
        self,
        owner,
        file_ref: str,
        user_id: str,
    ) -> "UploadedFile | None":
        return self._files.get(file_ref)

    async def get_file_by_id(self, file_id: str, user_id: str) -> "UploadedFile | None":
        ret = self._files.get(file_id)
        if ret is None:
            logger.info(
                f"File not found (mock StorageStub): {file_id}, user_id: {user_id} -- files: {self._files.keys()}"
            )
        return ret

    def add_file(self, file: "UploadedFile"):
        self._files[file.file_ref] = file
        self._files[file.file_id] = file

    async def get_thread(self, user_id: str, tid: str) -> ThreadStub:
        assert tid == self.thread.tid
        return self.thread

    async def list_data_frames(self, thread_id: str) -> "list[PlatformDataFrame]":
        assert thread_id == self.thread.tid, f"Thread ID mismatch: {thread_id} != {self.thread.tid}"
        return self.data_frames

    async def save_data_frame(self, data_frame: "PlatformDataFrame") -> None:
        self.data_frames.append(data_frame)

    async def delete_data_frame_by_name(self, thread_id: str, name: str) -> None:
        assert thread_id == self.thread.tid
        self.data_frames = [df for df in self.data_frames if df.name != name]

    async def create_in_memory_data_frame(self, name: str, contents: dict[str, list]):
        import datetime
        import io
        from uuid import uuid4

        import pyarrow.parquet

        from agent_platform.core.data_frames.data_frames import PlatformDataFrame
        from agent_platform.server.data_frames.data_node import convert_pyarrow_slice_to_table

        pyarrow_df = pyarrow.Table.from_pydict(contents)

        stream = io.BytesIO()
        pyarrow.parquet.write_table(pyarrow_df, stream)

        table = convert_pyarrow_slice_to_table(pyarrow_df, None, 10, None, None)
        sample_rows = table.rows[:10]

        self.data_frames.append(
            PlatformDataFrame(
                data_frame_id=str(uuid4()),
                name=name,
                user_id=self.thread.user.user_id,
                agent_id=self.thread.agent_id,
                thread_id=self.thread.tid,
                num_rows=pyarrow_df.shape[0],
                num_columns=pyarrow_df.shape[1],
                column_headers=list(pyarrow_df.schema.names),
                input_id_type="in_memory",
                created_at=datetime.datetime.now(datetime.UTC),
                parquet_contents=stream.getvalue(),
                computation_input_sources={},
                extra_data=PlatformDataFrame.build_extra_data(sample_rows=sample_rows),
            )
        )

    async def create_in_memory_data_frame_from_parquet_contents(self, name: str, contents: bytes):
        import datetime
        import io
        from uuid import uuid4

        import pyarrow.parquet

        from agent_platform.core.data_frames.data_frames import PlatformDataFrame

        # Read the parquet contents into a pyarrow table
        stream = io.BytesIO(contents)
        pyarrow_df = pyarrow.parquet.read_table(stream)

        self.data_frames.append(
            PlatformDataFrame(
                data_frame_id=str(uuid4()),
                name=name,
                user_id=self.thread.user.user_id,
                agent_id=self.thread.agent_id,
                thread_id=self.thread.tid,
                num_rows=pyarrow_df.shape[0],
                num_columns=pyarrow_df.shape[1],
                column_headers=list(pyarrow_df.schema.names),
                input_id_type="in_memory",
                created_at=datetime.datetime.now(datetime.UTC),
                parquet_contents=contents,
                computation_input_sources={},
            )
        )


class KernelStub:
    def __init__(self, thread: ThreadStub, user: UserStub):
        self.thread = thread
        self.user = user
        self.thread_state = None  # Add thread_state for new tools
        # Provide minimal agent attribute expected by interface
        self.agent = type("_Agent", (), {"extra": {}})()
