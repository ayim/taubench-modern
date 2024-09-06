"""Implementation of a langgraph checkpoint saver using Postgres."""

import abc
import os
import pickle
from contextlib import asynccontextmanager, contextmanager
from curses import meta
from typing import (
    Any,
    AsyncGenerator,
    AsyncIterator,
    Generator,
    List,
    Optional,
    Sequence,
    Tuple,
    cast,
)

import psycopg
from langchain_core.runnables import ConfigurableFieldSpec, RunnableConfig
from langgraph.checkpoint import BaseCheckpointSaver
from langgraph.checkpoint.base import (
    Checkpoint,
    CheckpointMetadata,
    CheckpointThreadTs,
    CheckpointTuple,
)
from psycopg_pool import AsyncConnectionPool, ConnectionPool


class PostgresSerializer(abc.ABC):
    """A serializer for serializing and deserializing objects to and from bytes."""

    @abc.abstractmethod
    def dumps(self, obj: Any) -> bytes:
        """Serialize an object to bytes."""

    @abc.abstractmethod
    def loads(self, data: bytes) -> Any:
        """Deserialize an object from bytes."""


class PicklePostgresSerializer(PostgresSerializer):
    """Use the pickle module to serialize and deserialize objects.

    This serializer uses the pickle module to serialize and deserialize objects.

    While pickling can serialize a wide range of Python objects, it may fail
    de-serializable objects upon updates of the Python version or the python
    environment (e.g., the object's class definition changes in LangGraph).

    *Security Warning*: The pickle module can deserialize malicious payloads,
        only use this serializer with trusted data; e.g., data that you
        have serialized yourself and can guarantee the integrity of.
    """

    def dumps(self, obj: Any) -> bytes:
        """Serialize an object to bytes."""
        return pickle.dumps(obj)

    def loads(self, data: bytes) -> Any:
        """Deserialize an object from bytes."""
        return pickle.loads(data)


def _get_dsn() -> str:
    """Get the DSN for the Postgres connection."""
    database = (os.environ["POSTGRES_DB"],)
    user = (os.environ["POSTGRES_USER"],)
    password = (os.environ["POSTGRES_PASSWORD"],)
    host = (os.environ["POSTGRES_HOST"],)
    port = (os.environ["POSTGRES_PORT"],)
    return f"postgresql://{user[0]}:{password[0]}@{host[0]}:{port[0]}/{database[0]}"


_sync_pool = None


@contextmanager
def _get_sync_connection() -> Generator[psycopg.Connection, None, None]:
    """Get the connection to the Postgres database."""
    global _sync_pool
    if _sync_pool is None:
        _sync_pool = ConnectionPool(
            conninfo=_get_dsn(),
            max_size=20,
        )
    with _sync_pool.connection() as conn:
        yield conn


_async_pool = None


@asynccontextmanager
async def _get_async_connection() -> AsyncGenerator[psycopg.AsyncConnection, None]:
    """Get the connection to the Postgres database."""
    global _async_pool
    if _async_pool is None:
        print("Initializing async_connection")
        conn_info = _get_dsn()
        _async_pool = AsyncConnectionPool(
            conninfo=conn_info,
            max_size=20,
        )
    async with _async_pool.connection() as conn:
        yield conn


class PostgresSaver(BaseCheckpointSaver):
    """A checkpoint saver that uses Postgres to save checkpoints."""

    serde: PostgresSerializer
    """The serializer for serializing and deserializing objects to and from bytes."""

    class Config:
        arbitrary_types_allowed = True
        extra = "forbid"

    @property
    def config_specs(self) -> list[ConfigurableFieldSpec]:
        """Return the configuration specs for this runnable."""
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
    def _get_sync_connection(self) -> Generator[psycopg.Connection, None, None]:
        """Get the connection to the Postgres database."""
        with _get_sync_connection() as connection:
            yield connection

    @asynccontextmanager
    async def _get_async_connection(
        self,
    ) -> AsyncGenerator[psycopg.AsyncConnection, None]:
        """Get the connection to the Postgres database."""
        async with _get_async_connection() as connection:
            yield connection

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
    ) -> RunnableConfig:
        """Put the checkpoint for the given configuration.

        Args:
            config: The configuration for the checkpoint.
                A dict with a `configurable` key which is a dict with
                a `thread_id` key and an optional `thread_ts` key.
                For example, { 'configurable': { 'thread_id': 'test_thread' } }
            checkpoint: The checkpoint to persist.

        Returns:
            The RunnableConfig that describes the checkpoint that was just created.
            It'll contain the `thread_id` and `thread_ts` of the checkpoint.
        """
        thread_id = config["configurable"]["thread_id"]
        parent_ts = config["configurable"].get("thread_ts")

        with self._get_sync_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO checkpoints 
                        (thread_id, thread_ts, parent_ts, checkpoint, metadata)
                    VALUES 
                        (%(thread_id)s, %(thread_ts)s, %(parent_ts)s, %(checkpoint)s, %(metadata)s)
                    ON CONFLICT (thread_id, thread_ts) 
                    DO UPDATE SET 
                        checkpoint = EXCLUDED.checkpoint,
                        metadata = EXCLUDED.metadata;
                    """,
                    {
                        "thread_id": thread_id,
                        "thread_ts": checkpoint["ts"],
                        "parent_ts": parent_ts if parent_ts else None,
                        "checkpoint": self.serde.dumps(checkpoint),
                        "metadata": self.serde.dumps(metadata),
                    },
                )

        return {
            "configurable": {
                "thread_id": thread_id,
                "thread_ts": checkpoint["ts"],
            },
        }

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
    ) -> RunnableConfig:
        """Put the checkpoint for the given configuration.

        Args:
            config: The configuration for the checkpoint.
                A dict with a `configurable` key which is a dict with
                a `thread_id` key and an optional `thread_ts` key.
                For example, { 'configurable': { 'thread_id': 'test_thread' } }
            checkpoint: The checkpoint to persist.

        Returns:
            The RunnableConfig that describes the checkpoint that was just created.
            It'll contain the `thread_id` and `thread_ts` of the checkpoint.
        """
        thread_id = config["configurable"]["thread_id"]
        parent_ts = config["configurable"].get("thread_ts")
        async with self._get_async_connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO checkpoints 
                        (thread_id, thread_ts, parent_ts, checkpoint, metadata)
                    VALUES 
                        (%(thread_id)s, %(thread_ts)s, %(parent_ts)s, %(checkpoint)s, %(metadata)s)
                    ON CONFLICT (thread_id, thread_ts) 
                    DO UPDATE SET 
                        checkpoint = EXCLUDED.checkpoint,
                        metadata = EXCLUDED.metadata;
                    """,
                    {
                        "thread_id": thread_id,
                        "thread_ts": checkpoint["ts"],
                        "parent_ts": parent_ts if parent_ts else None,
                        "checkpoint": self.serde.dumps(checkpoint),
                        "metadata": self.serde.dumps(metadata),
                    },
                )

        return {
            "configurable": {
                "thread_id": thread_id,
                "thread_ts": checkpoint["ts"],
            },
        }

    def list(self, config: RunnableConfig) -> Generator[CheckpointTuple, None, None]:
        """Get all the checkpoints for the given configuration."""
        with self._get_sync_connection() as conn:
            with conn.cursor() as cur:
                thread_id = config["configurable"]["thread_id"]
                cur.execute(
                    "SELECT checkpoint, metadata, thread_ts, parent_ts "
                    "FROM checkpoints "
                    "WHERE thread_id = %(thread_id)s "
                    "ORDER BY thread_ts DESC",
                    {
                        "thread_id": thread_id,
                    },
                )
                for value in cur:
                    yield CheckpointTuple(
                        config={
                            "configurable": {
                                "thread_id": thread_id,
                                "thread_ts": value[2],
                            }
                        },
                        checkpoint=cast(Checkpoint, self.serde.loads(value[0])),
                        metadata=cast(CheckpointMetadata, self.serde.loads(value[1])),
                        parent_config={
                            "configurable": {
                                "thread_id": thread_id,
                                "thread_ts": value[3],
                            }
                        }
                        if value[3]
                        else None,
                    )

    async def alist(self, config: RunnableConfig) -> AsyncIterator[CheckpointTuple]:
        """Get all the checkpoints for the given configuration."""
        async with self._get_async_connection() as conn:
            async with conn.cursor() as cur:
                thread_id = config["configurable"]["thread_id"]
                await cur.execute(
                    "SELECT checkpoint, metadata, thread_ts, parent_ts "
                    "FROM checkpoints "
                    "WHERE thread_id = %(thread_id)s "
                    "ORDER BY thread_ts DESC",
                    {
                        "thread_id": thread_id,
                    },
                )
                async for value in cur:
                    yield CheckpointTuple(
                        config={
                            "configurable": {
                                "thread_id": thread_id,
                                "thread_ts": value[2],
                            }
                        },
                        checkpoint=cast(Checkpoint, self.serde.loads(value[0])),
                        metadata=cast(CheckpointMetadata, self.serde.loads(value[1])),
                        parent_config={
                            "configurable": {
                                "thread_id": thread_id,
                                "thread_ts": value[3],
                            }
                        }
                        if value[3]
                        else None,
                    )

    def get_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """Get the checkpoint tuple for the given configuration.

        Args:
            config: The configuration for the checkpoint.
                A dict with a `configurable` key which is a dict with
                a `thread_id` key and an optional `thread_ts` key.
                For example, { 'configurable': { 'thread_id': 'test_thread' } }

        Returns:
            The checkpoint tuple for the given configuration if it exists,
            otherwise None.

            If thread_ts is None, the latest checkpoint is returned if it exists.
        """
        thread_id = config["configurable"]["thread_id"]
        thread_ts = config["configurable"].get("thread_ts")
        with self._get_sync_connection() as conn:
            with conn.cursor() as cur:
                # get the checkpoint requested or return the latest checkpoint
                if thread_ts:
                    cur.execute(
                        "SELECT thread_id, thread_ts, parent_ts, checkpoint, metadata "
                        "FROM checkpoints "
                        "WHERE thread_id = %(thread_id)s AND thread_ts = %(thread_ts)s",
                        {
                            "thread_id": thread_id,
                            "thread_ts": thread_ts,
                        },
                    )
                else:
                    cur.execute(
                        "SELECT thread_id, thread_ts, parent_ts, checkpoint, metadata "
                        "FROM checkpoints "
                        "WHERE thread_id = %(thread_id)s "
                        "ORDER BY thread_ts DESC LIMIT 1",
                        {
                            "thread_id": thread_id,
                        },
                    )
                try:
                    value = cur.fetchone()
                except psycopg.ProgrammingError:
                    return None
                if value:
                    if not thread_ts:
                        config = {
                            "configurable": {
                                "thread_id": value[0],
                                "thread_ts": value[1],
                            }
                        }
                        thread_id = value[0]
                        thread_ts = value[1]
                    # find any pending writes
                    cur.execute(
                        "SELECT task_id, channel, value "
                        "FROM writes "
                        "WHERE thread_id = %(thread_id)s AND thread_ts = %(thread_ts)s",
                        {
                            "thread_id": thread_id,
                            "thread_ts": thread_ts,
                        },
                    )
                    if value[4] is not None:
                        metadata = cast(CheckpointMetadata, self.serde.loads(value[4]))
                    else:
                        metadata = {}
                    return CheckpointTuple(
                        config=config,
                        checkpoint=cast(Checkpoint, self.serde.loads(value[3])),
                        metadata=metadata,
                        parent_config={
                            "configurable": {
                                "thread_id": thread_id,
                                "thread_ts": value[2],
                            }
                        }
                        if value[2]
                        else None,
                        pending_writes=[
                            (task_id, channel, self.serde.loads(value))
                            for task_id, channel, value in cur
                        ],
                    )
        return None

    async def aget_tuple(self, config: RunnableConfig) -> Optional[CheckpointTuple]:
        """Get the checkpoint tuple for the given configuration.

        Args:
            config: The configuration for the checkpoint.
                A dict with a `configurable` key which is a dict with
                a `thread_id` key and an optional `thread_ts` key.
                For example, { 'configurable': { 'thread_id': 'test_thread' } }

        Returns:
            The checkpoint tuple for the given configuration if it exists,
            otherwise None.

            If thread_ts is None, the latest checkpoint is returned if it exists.
        """
        thread_id = config["configurable"]["thread_id"]
        thread_ts = config["configurable"].get("thread_ts")
        async with self._get_async_connection() as conn:
            async with conn.cursor() as cur:
                # get the checkpoint requested or return the latest checkpoint
                if thread_ts:
                    cur.execute(
                        "SELECT thread_id, thread_ts, parent_ts, checkpoint, metadata "
                        "FROM checkpoints "
                        "WHERE thread_id = %(thread_id)s AND thread_ts = %(thread_ts)s",
                        {
                            "thread_id": thread_id,
                            "thread_ts": thread_ts,
                        },
                    )
                else:
                    cur.execute(
                        "SELECT thread_id, thread_ts, parent_ts, checkpoint, metadata "
                        "FROM checkpoints "
                        "WHERE thread_id = %(thread_id)s "
                        "ORDER BY thread_ts DESC LIMIT 1",
                        {
                            "thread_id": thread_id,
                        },
                    )
                try:
                    value = await cur.fetchone()
                except psycopg.ProgrammingError:
                    return None
                if value:
                    if not thread_ts:
                        config = {
                            "configurable": {
                                "thread_id": value[0],
                                "thread_ts": value[1],
                            }
                        }
                        thread_id = value[0]
                        thread_ts = value[1]
                    # find any pending writes
                    cur.execute(
                        "SELECT task_id, channel, value "
                        "FROM writes "
                        "WHERE thread_id = %(thread_id)s AND thread_ts = %(thread_ts)s",
                        {
                            "thread_id": thread_id,
                            "thread_ts": thread_ts,
                        },
                    )
                    if value[4] is not None:
                        metadata = cast(CheckpointMetadata, self.serde.loads(value[4]))
                    else:
                        metadata = {}
                    return CheckpointTuple(
                        config=config,
                        checkpoint=cast(Checkpoint, self.serde.loads(value[3])),
                        metadata=metadata,
                        parent_config={
                            "configurable": {
                                "thread_id": thread_id,
                                "thread_ts": value[2],
                            }
                        }
                        if value[2]
                        else None,
                        pending_writes=[
                            (task_id, channel, self.serde.loads(val))
                            for task_id, channel, val in await cur.fetchall()
                        ],
                    )

        return None

    def put_writes(
        self, config: RunnableConfig, writes: Sequence[tuple[str, Any]], task_id: str
    ) -> None:
        """Put the writes for the given configuration.

        Args:
            config: The configuration for the writes.
                A dict with a `configurable` key which is a dict with
                a `thread_id` key and an optional `thread_ts` key.
                For example, { 'configurable': { 'thread_id': 'test_thread' } }
            writes: The writes to persist.
            task_id: The task ID for the writes.
        """
        thread_id = config["configurable"]["thread_id"]
        thread_ts = config["configurable"]["thread_ts"]

        with self._get_sync_connection() as conn:
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO writes 
                        (thread_id, thread_ts, task_id, idx, channel, value)
                    VALUES 
                        (%(thread_id)s, %(thread_ts)s, %(task_id)s, %(idx)s, %(channel)s, %(value)s)
                    ON CONFLICT (thread_id, thread_ts, task_id, idx) 
                    DO UPDATE SET 
                        channel = EXCLUDED.channel,
                        value = EXCLUDED.value;
                    """,
                    [
                        {
                            "thread_id": thread_id,
                            "thread_ts": thread_ts,
                            "task_id": task_id,
                            "idx": idx,
                            "channel": channel,
                            "value": self.serde.dumps(value),
                        }
                        for idx, (channel, value) in enumerate(writes)
                    ],
                )

    async def aput_writes(
        self, config: RunnableConfig, writes: List[Tuple[str | Any]], task_id: str
    ) -> None:
        """Put the writes for the given configuration.

        Args:
            config: The configuration for the writes.
                A dict with a `configurable` key which is a dict with
                a `thread_id` key and an optional `thread_ts` key.
                For example, { 'configurable': { 'thread_id': 'test_thread' } }
            writes: The writes to persist.
            task_id: The task ID for the writes.
        """
        thread_id = config["configurable"]["thread_id"]
        thread_ts = config["configurable"]["thread_ts"]

        async with self._get_async_connection() as conn:
            async with conn.cursor() as cur:
                await cur.executemany(
                    """
                    INSERT INTO writes 
                        (thread_id, thread_ts, task_id, idx, channel, value)
                    VALUES 
                        (%(thread_id)s, %(thread_ts)s, %(task_id)s, %(idx)s, %(channel)s, %(value)s)
                    ON CONFLICT (thread_id, thread_ts, task_id, idx) 
                    DO UPDATE SET 
                        channel = EXCLUDED.channel,
                        value = EXCLUDED.value;
                    """,
                    [
                        {
                            "thread_id": thread_id,
                            "thread_ts": thread_ts,
                            "task_id": task_id,
                            "idx": idx,
                            "channel": channel,
                            "value": self.serde.dumps(value),
                        }
                        for idx, (channel, value) in enumerate(writes)
                    ],
                )


class PostgresCheckpointer(PostgresSaver):
    serde = None

    def __init__(self, serializer: PostgresSerializer):
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
