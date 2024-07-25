import os
import pickle
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Iterator, Optional

from langchain_core.messages import BaseMessage
from langchain_core.runnables import ConfigurableFieldSpec, RunnableConfig
from langgraph.checkpoint import (
    BaseCheckpointSaver,
    Checkpoint,
)
from langgraph.checkpoint.base import CheckpointThreadTs, CheckpointTuple

from app.constants import DOMAIN_DATABASE_PATH
from app.storage.postgres_checkpointer import (
    CheckpointSerializer,
    PickleCheckpointSerializer,
    PostgresSaver,
)


class PostgresCheckpointer(PostgresSaver):
    serde = None

    def __init__(self, serializer: CheckpointSerializer):
        super().__init__()
        self.serde = serializer
        # self.sync_connection = sync_connection
        # self.async_connection = async_connection

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
        self, config: RunnableConfig, checkpoint: Checkpoint
    ) -> RunnableConfig:
        return self.put(config, checkpoint)

    async def alist(self, config: RunnableConfig) -> Iterator[CheckpointTuple]:
        return self.list(config)

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        with self.cursor(transaction=False) as cur:
            if config["configurable"].get("thread_ts"):
                cur.execute(
                    "SELECT checkpoint, parent_ts FROM checkpoints WHERE thread_id = ? AND thread_ts = ?",
                    (
                        config["configurable"]["thread_id"],
                        config["configurable"]["thread_ts"],
                    ),
                )
                if value := cur.fetchone():
                    return CheckpointTuple(
                        config,
                        self.loads(value[0]),
                        {
                            "configurable": {
                                "thread_id": config["configurable"]["thread_id"],
                                "thread_ts": value[1],
                            }
                        }
                        if value[1]
                        else None,
                    )
            else:
                cur.execute(
                    "SELECT thread_id, thread_ts, parent_ts, checkpoint FROM checkpoints WHERE thread_id = ? ORDER BY thread_ts DESC LIMIT 1",
                    (config["configurable"]["thread_id"],),
                )
                if value := cur.fetchone():
                    return CheckpointTuple(
                        {
                            "configurable": {
                                "thread_id": value[0],
                                "thread_ts": value[1],
                            }
                        },
                        self.loads(value[3]),
                        {
                            "configurable": {
                                "thread_id": value[0],
                                "thread_ts": value[2],
                            }
                        }
                        if value[2]
                        else None,
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

    def put(self, config: RunnableConfig, checkpoint: Checkpoint) -> RunnableConfig:
        thread_id = config["configurable"]["thread_id"]
        thread_ts = checkpoint["ts"]
        parent_ts = config["configurable"].get("thread_ts")

        thread_ts = (
            thread_ts.isoformat() if isinstance(thread_ts, datetime) else thread_ts
        )
        parent_ts = (
            parent_ts.isoformat() if isinstance(parent_ts, datetime) else parent_ts
        )

        if isinstance(parent_ts, list):
            parent_ts = None

        with self.cursor() as cur:
            cur.execute(
                "INSERT OR REPLACE INTO checkpoints (thread_id, thread_ts, parent_ts, checkpoint) VALUES (?, ?, ?, ?)",
                (thread_id, thread_ts, parent_ts, pickle.dumps(checkpoint)),
            )

        return {
            "configurable": {
                "thread_id": thread_id,
                "thread_ts": checkpoint["ts"],
            }
        }


_checkpointer = None


def get_checkpointer() -> BaseCheckpointSaver:
    db_type = os.environ.get("S4_AGENT_SERVER_DB_TYPE", "sqlite")
    global _checkpointer
    if _checkpointer is None:
        if db_type == "postgres":
            _checkpointer = PostgresCheckpointer(
                serializer=PickleCheckpointSerializer(),
            )
        elif db_type == "sqlite":
            _checkpointer = SQLiteCheckpoint()
        else:
            raise ValueError(f"Invalid storage type: {db_type}")
    return _checkpointer
