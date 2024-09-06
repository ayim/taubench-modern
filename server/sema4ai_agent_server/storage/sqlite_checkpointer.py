import pickle
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator, Optional, Sequence

from langchain_core.messages import BaseMessage
from langchain_core.runnables import ConfigurableFieldSpec, RunnableConfig
from langgraph.checkpoint import (
    BaseCheckpointSaver,
    Checkpoint,
)
from langgraph.checkpoint.base import (
    CheckpointMetadata,
    CheckpointThreadTs,
    CheckpointTuple,
)

from sema4ai_agent_server.constants import DOMAIN_DATABASE_PATH


@contextmanager
def _connect_sqlite():
    conn = sqlite3.connect(DOMAIN_DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Enable dictionary access to row items.
    try:
        yield conn
    finally:
        conn.close()


class SQLiteCheckpoint(BaseCheckpointSaver):
    serde = None

    def loads(self, value: bytes) -> Checkpoint:
        loaded: Checkpoint = pickle.loads(value)
        for key, value in loaded["channel_values"].items():
            if isinstance(value, list) and all(
                isinstance(v, BaseMessage) for v in value
            ):
                loaded["channel_values"][key] = [
                    v.__class__(**v.__dict__) for v in value
                ]
        return loaded

    @property
    def config_specs(self) -> list[ConfigurableFieldSpec]:
        return [
            ConfigurableFieldSpec(
                id="thread_id",
                annotation=Optional[str],
                name="Thread ID",
                description=None,
                default=None,
                is_shared=True,
            ),
            CheckpointThreadTs,
        ]

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

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        return self.get_tuple(config)

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
    ) -> RunnableConfig:
        return self.put(config, checkpoint, metadata)

    async def alist(self, config: RunnableConfig) -> Iterator[CheckpointTuple]:
        return self.list(config)

    async def aput_writes(
        self, config: RunnableConfig, writes: list[tuple[str, Any]], task_id: str
    ) -> None:
        return self.put_writes(config, writes, task_id)

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        with self.cursor(transaction=False) as cur:
            # find the latest checkpoint for the thread_id
            if config["configurable"].get("thread_ts"):
                cur.execute(
                    "SELECT thread_id, thread_ts, parent_ts, checkpoint, metadata FROM checkpoints WHERE thread_id = ? AND thread_ts = ?",
                    (
                        str(config["configurable"]["thread_id"]),
                        str(config["configurable"]["thread_ts"]),
                    ),
                )
            else:
                cur.execute(
                    "SELECT thread_id, thread_ts, parent_ts, checkpoint, metadata FROM checkpoints WHERE thread_id = ? ORDER BY thread_ts DESC LIMIT 1",
                    (str(config["configurable"]["thread_id"]),),
                )
            # if a checkpoint is found, return it
            if value := cur.fetchone():
                if not config["configurable"].get("thread_ts"):
                    config = {
                        "configurable": {
                            "thread_id": value[0],
                            "thread_ts": value[1],
                        }
                    }
                # find any pending writes
                cur.execute(
                    "SELECT task_id, channel, value FROM writes WHERE thread_id = ? AND thread_ts = ?",
                    (
                        str(config["configurable"]["thread_id"]),
                        str(config["configurable"]["thread_ts"]),
                    ),
                )
                # deserialize the checkpoint and metadata
                return CheckpointTuple(
                    config,
                    self.loads(value[3]),
                    pickle.loads(value[4]) if value[4] is not None else {},
                    (
                        {
                            "configurable": {
                                "thread_id": value[0],
                                "thread_ts": value[2],
                            }
                        }
                        if value[2]
                        else None
                    ),
                    [
                        (task_id, channel, pickle.loads(value))
                        for task_id, channel, value in cur
                    ],
                )

    def list(self, config: RunnableConfig) -> Iterator[CheckpointTuple]:
        with self.cursor(transaction=False) as cur:
            cur.execute(
                "SELECT thread_id, thread_ts, parent_ts, checkpoint FROM checkpoints WHERE thread_id = ? ORDER BY thread_ts DESC",
                (config["configurable"]["thread_id"],),
            )
            for thread_id, thread_ts, parent_ts, value in cur:
                yield CheckpointTuple(
                    {"configurable": {"thread_id": thread_id, "thread_ts": thread_ts}},
                    self.loads(value),
                    {
                        "configurable": {
                            "thread_id": thread_id,
                            "thread_ts": parent_ts,
                        }
                    }
                    if parent_ts
                    else None,
                )

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
    ) -> RunnableConfig:
        thread_id = config["configurable"]["thread_id"]
        thread_ts = checkpoint["ts"]
        parent_ts = config["configurable"].get("thread_ts")

        if isinstance(parent_ts, list):
            parent_ts = None

        with self.cursor() as cur:
            cur.execute(
                "INSERT OR REPLACE INTO checkpoints (thread_id, thread_ts, parent_ts, checkpoint, metadata) VALUES (?, ?, ?, ?, ?)",
                (
                    thread_id,
                    thread_ts,
                    parent_ts,
                    pickle.dumps(checkpoint),
                    pickle.dumps(metadata),
                ),
            )

        return {
            "configurable": {
                "thread_id": thread_id,
                "thread_ts": checkpoint["ts"],
            }
        }

    def put_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
    ) -> None:
        with self.cursor() as cur:
            cur.executemany(
                "INSERT OR REPLACE INTO writes (thread_id, thread_ts, task_id, idx, channel, value) VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        str(config["configurable"]["thread_id"]),
                        str(config["configurable"]["thread_ts"]),
                        task_id,
                        idx,
                        channel,
                        pickle.dumps(value),
                    )
                    for idx, (channel, value) in enumerate(writes)
                ],
            )
