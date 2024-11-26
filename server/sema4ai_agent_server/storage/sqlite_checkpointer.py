import sqlite3
from contextlib import closing, contextmanager
from typing import Any, Dict, Iterator, Sequence

from langchain_core.messages import BaseMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    get_checkpoint_id,
)
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from sema4ai_agent_server.constants import DOMAIN_DATABASE_PATH
from sema4ai_agent_server.schema import AgentServerRunnableConfig
from sema4ai_agent_server.storage.utils import search_where
from sema4ai_agent_server.utils import (
    convert_runnable_to_langchain,
    get_thread_id_from_config,
)


@contextmanager
def _connect_sqlite():
    conn = sqlite3.connect(DOMAIN_DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Enable dictionary access to row items.
    try:
        yield conn
    finally:
        conn.close()


class SQLiteCheckpoint(BaseCheckpointSaver):
    serde = JsonPlusSerializer()

    def load_checkpoint(self, value: bytes) -> Checkpoint:
        loaded: Checkpoint = self.serde.loads(value)
        for key, value in loaded["channel_values"].items():
            if isinstance(value, list) and all(
                isinstance(v, BaseMessage) for v in value
            ):
                loaded["channel_values"][key] = [
                    v.__class__(**v.__dict__) for v in value
                ]
        return loaded

    def load_metadata(self, value: bytes | None) -> CheckpointMetadata | Dict:
        return self.serde.loads(value)

    def loads(self, data: bytes) -> Any:
        return self.serde.loads(data)

    def dumps(self, obj: Any) -> bytes:
        return self.serde.dumps(obj)

    @contextmanager
    def cursor(self, transaction: bool = True):
        with _connect_sqlite() as conn:
            cur = conn.cursor()
            try:
                yield cur
            finally:
                if transaction:
                    conn.commit()
                cur.close()

    async def aget_tuple(
        self, config: AgentServerRunnableConfig | RunnableConfig
    ) -> CheckpointTuple | None:
        return self.get_tuple(config)

    async def aput(
        self,
        config: AgentServerRunnableConfig | RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        return self.put(config, checkpoint, metadata, new_versions)

    async def alist(
        self,
        config: AgentServerRunnableConfig | RunnableConfig | None,
        *,
        filter: Dict[str, Any] | None = None,
        before: AgentServerRunnableConfig | RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        return self.list(config, filter=filter, before=before, limit=limit)

    async def aput_writes(
        self,
        config: AgentServerRunnableConfig | RunnableConfig,
        writes: list[tuple[str, Any]],
        task_id: str,
    ) -> None:
        return self.put_writes(config, writes, task_id)

    def get_tuple(
        self, config: AgentServerRunnableConfig | RunnableConfig
    ) -> CheckpointTuple | None:
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        with self.cursor(transaction=False) as cur:
            # find the latest checkpoint for the thread_id
            if checkpoint_id := get_checkpoint_id(config):
                cur.execute(
                    "SELECT thread_id, checkpoint_id, parent_checkpoint_id, checkpoint, metadata FROM checkpoints WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id = ?",
                    (
                        get_thread_id_from_config(config),
                        checkpoint_ns,
                        checkpoint_id,
                    ),
                )
            else:
                cur.execute(
                    "SELECT thread_id, checkpoint_id, parent_checkpoint_id, checkpoint, metadata FROM checkpoints WHERE thread_id = ? AND checkpoint_ns = ? ORDER BY checkpoint_id DESC LIMIT 1",
                    (get_thread_id_from_config(config), checkpoint_ns),
                )
            # if a checkpoint is found, return it
            if value := cur.fetchone():
                thread_id, checkpoint_id, parent_checkpoint_id, checkpoint, metadata = (
                    value
                )
                if not get_checkpoint_id(config):
                    config = {
                        "configurable": {
                            "thread_id": thread_id,
                            "checkpoint_ns": checkpoint_ns,
                            "checkpoint_id": checkpoint_id,
                        }
                    }
                # find any pending writes
                cur.execute(
                    "SELECT task_id, channel, value FROM writes WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id = ? ORDER BY task_id, idx",
                    (
                        get_thread_id_from_config(config),
                        checkpoint_ns,
                        get_checkpoint_id(config),
                    ),
                )
                # deserialize the checkpoint and metadata
                return CheckpointTuple(
                    config,
                    self.load_checkpoint(checkpoint),
                    self.load_metadata(metadata),
                    (
                        {
                            "configurable": {
                                "thread_id": thread_id,
                                "checkpoint_ns": checkpoint_ns,
                                "checkpoint_id": parent_checkpoint_id,
                            }
                        }
                        if parent_checkpoint_id
                        else None
                    ),
                    [
                        (task_id, channel, self.loads(value))
                        for task_id, channel, value in cur
                    ],
                )
        return None

    def list(
        self,
        config: AgentServerRunnableConfig | RunnableConfig | None,
        *,
        filter: Dict[str, Any] | None = None,
        before: AgentServerRunnableConfig | RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        where, param_values = search_where(config, filter, before, flavor="sqlite")
        query = f"""SELECT thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, checkpoint, metadata
        FROM checkpoints
        {where}
        ORDER BY checkpoint_id DESC"""
        if limit:
            query += f" LIMIT {limit}"
        with self.cursor(transaction=False) as cur, _connect_sqlite() as wconn:
            with closing(wconn.cursor()) as wcur:
                cur.execute(query, param_values)
                for (
                    thread_id,
                    checkpoint_ns,
                    checkpoint_id,
                    parent_checkpoint_id,
                    checkpoint,
                    metadata,
                ) in cur:
                    wcur.execute(
                        "SELECT task_id, channel, value FROM writes WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id = ? ORDER BY task_id, idx",
                        (
                            thread_id,
                            checkpoint_ns,
                            checkpoint_id,
                        ),
                    )
                    yield CheckpointTuple(
                        {
                            "configurable": {
                                "thread_id": thread_id,
                                "checkpoint_ns": checkpoint_ns,
                                "checkpoint_id": checkpoint_id,
                            }
                        },
                        self.load_checkpoint(checkpoint),
                        self.load_metadata(metadata),
                        (
                            {
                                "configurable": {
                                    "thread_id": thread_id,
                                    "checkpoint_ns": checkpoint_ns,
                                    "checkpoint_id": parent_checkpoint_id,
                                }
                            }
                            if parent_checkpoint_id
                            else None
                        ),
                        [
                            (task_id, channel, self.loads(value))
                            for task_id, channel, value in wcur
                        ],
                    )

    def put(
        self,
        config: AgentServerRunnableConfig | RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        thread_id = get_thread_id_from_config(config)
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        parent_checkpoint_id = config["configurable"].get("checkpoint_id")
        serialized_checkpoint = self.dumps(checkpoint)
        serialized_metadata = self.dumps(metadata)

        with self.cursor() as cur:
            cur.execute(
                "INSERT OR REPLACE INTO checkpoints (thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, checkpoint, metadata) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    thread_id,
                    checkpoint_ns,
                    checkpoint["id"],
                    parent_checkpoint_id,
                    serialized_checkpoint,
                    serialized_metadata,
                ),
            )
        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint["id"],
            }
        }

    def put_writes(
        self,
        config: AgentServerRunnableConfig | RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
    ) -> None:
        query = (
            "INSERT OR REPLACE INTO writes (thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, value) VALUES (?, ?, ?, ?, ?, ?, ?)"
            if all(w[0] in WRITES_IDX_MAP for w in writes)
            else "INSERT OR IGNORE INTO writes (thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, value) VALUES (?, ?, ?, ?, ?, ?, ?)"
        )
        with self.cursor() as cur:
            cur.executemany(
                query,
                [
                    (
                        get_thread_id_from_config(config),
                        str(config["configurable"].get("checkpoint_ns", "")),
                        get_checkpoint_id(config),
                        task_id,
                        WRITES_IDX_MAP.get(channel, idx),
                        channel,
                        self.dumps(value),
                    )
                    for idx, (channel, value) in enumerate(writes)
                ],
            )
