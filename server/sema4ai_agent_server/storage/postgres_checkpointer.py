"""Implementation of a langgraph checkpoint saver using Postgres."""

import abc
import pickle
from typing import (
    Any,
    AsyncIterator,
    Iterator,
    List,
    Sequence,
    Tuple,
    cast,
)

import psycopg
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
from pydantic import ConfigDict

from sema4ai_agent_server.storage.postgres_conn import PostgresConnectionManager
from sema4ai_agent_server.storage.utils import search_where


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


class PostgresSaver(BaseCheckpointSaver, PostgresConnectionManager):
    """A checkpoint saver that uses Postgres to save checkpoints."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    serde: PostgresSerializer
    """The serializer for serializing and deserializing objects to and from bytes."""

    UPSERT_CHECKPOINT_SQL = """
        INSERT INTO checkpoints 
            (thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, checkpoint, metadata)
        VALUES 
            (%(thread_id)s, %(checkpoint_ns)s, %(checkpoint_id)s, %(parent_checkpoint_id)s, 
            %(checkpoint)s, %(metadata)s)
        ON CONFLICT (thread_id, checkpoint_ns, checkpoint_id)
        DO UPDATE SET
            checkpoint = EXCLUDED.checkpoint,
            metadata = EXCLUDED.metadata;
    """
    UPSERT_WRITES_SQL = """
        INSERT INTO writes
            (thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, value)
        VALUES
            (%(thread_id)s, %(checkpoint_ns)s, %(checkpoint_id)s, %(task_id)s, %(idx)s,
            %(channel)s, %(value)s)
        ON CONFLICT (thread_id, checkpoint_ns, checkpoint_id, task_id, idx) DO UPDATE SET
            channel = EXCLUDED.channel,
            value = EXCLUDED.value;
    """
    INSERT_WRITES_SQL = """
        INSERT INTO writes
            (thread_id, checkpoint_ns, checkpoint_id, task_id, idx, channel, value)
        VALUES
            (%(thread_id)s, %(checkpoint_ns)s, %(checkpoint_id)s, %(task_id)s, %(idx)s,
            %(channel)s, %(value)s)
        ON CONFLICT (thread_id, checkpoint_ns, checkpoint_id, task_id, idx) DO NOTHING;
    """
    SELECT_CHECKPOINT_SQL = """
        SELECT thread_id, checkpoint_id, parent_checkpoint_id, checkpoint, metadata
        FROM checkpoints
        WHERE thread_id = %(thread_id)s AND checkpoint_ns = %(checkpoint_ns)s
            AND checkpoint_id = %(checkpoint_id)s
    """
    SELECT_RECENT_CHECKPOINT_SQL = """
        SELECT thread_id, checkpoint_id, parent_checkpoint_id, checkpoint, metadata
        FROM checkpoints
        WHERE thread_id = %(thread_id)s AND checkpoint_ns = %(checkpoint_ns)s
        ORDER BY checkpoint_id DESC LIMIT 1
    """
    SELECT_CHECKPOINTS_TEMPLATE = """
        SELECT thread_id, checkpoint_ns, checkpoint_id, parent_checkpoint_id, checkpoint, metadata
        FROM checkpoints
        {where}
        ORDER BY checkpoint_id DESC
    """
    SELECT_WRITES_SQL = """
        SELECT task_id, channel, value
        FROM writes
        WHERE thread_id = %(thread_id)s AND checkpoint_ns = %(checkpoint_ns)s
            AND checkpoint_id = %(checkpoint_id)s
        ORDER BY task_id, idx
    """

    def _dump_writes(
        self,
        thread_id: str,
        checkpoint_ns: str,
        checkpoint_id: str,
        task_id: str,
        writes: Sequence[Tuple[str, Any]],
    ) -> list[dict[str, str | bytes]]:
        return [
            {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint_id,
                "task_id": task_id,
                "idx": WRITES_IDX_MAP.get(channel, idx),
                "channel": channel,
                "value": self.serde.dumps(value),
            }
            for idx, (channel, value) in enumerate(writes)
        ]

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Save a checkpoint to the database.

        This method saves a checkpoint to the Postgres database. The checkpoint is associated
        with the provided config and its parent config (if any).

        Args:
            config (RunnableConfig): The config associated with the checkpoint.
            checkpoint (Checkpoint): The checkpoint to persist.
            metadata (CheckpointMetadata): Additional metadata to save with the checkpoint.
            new_versions (ChannelVersions): New channel versions as of this write.

        Returns:
            RunnableConfig: Updated configuration after storing the checkpoint.
        """
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"]["checkpoint_ns"]
        parent_checkpoint_id = config["configurable"].get("checkpoint_id")

        with self.sync_cursor() as cur:
            cur.execute(
                self.UPSERT_CHECKPOINT_SQL,
                {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": checkpoint["id"],
                    "parent_checkpoint_id": parent_checkpoint_id,
                    "checkpoint": self.serde.dumps(checkpoint),
                    "metadata": self.serde.dumps(metadata),
                },
            )

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint["id"],
            },
        }

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        """Save a checkpoint to the database.

        This method saves a checkpoint to the Postgres database. The checkpoint is associated
        with the provided config and its parent config (if any).

        Args:
            config (RunnableConfig): The config associated with the checkpoint.
            checkpoint (Checkpoint): The checkpoint to persist.
            metadata (CheckpointMetadata): Additional metadata to save with the checkpoint.
            new_versions (ChannelVersions): New channel versions as of this write.

        Returns:
            RunnableConfig: Updated configuration after storing the checkpoint.
        """
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"]["checkpoint_ns"]
        parent_checkpoint_id = config["configurable"].get("checkpoint_id")

        async with self.async_cursor() as cur:
            await cur.execute(
                self.UPSERT_CHECKPOINT_SQL,
                {
                    "thread_id": thread_id,
                    "checkpoint_ns": checkpoint_ns,
                    "checkpoint_id": checkpoint["id"],
                    "parent_checkpoint_id": parent_checkpoint_id,
                    "checkpoint": self.serde.dumps(checkpoint),
                    "metadata": self.serde.dumps(metadata),
                },
            )

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": checkpoint_ns,
                "checkpoint_id": checkpoint["id"],
            },
        }

    def put_writes(
        self, config: RunnableConfig, writes: Sequence[tuple[str, Any]], task_id: str
    ) -> None:
        """Store intermediate writes linked to a checkpoint.

        This method saves intermediate writes associated with a checkpoint to the Postgres database.

        Args:
            config (RunnableConfig): Configuration of the related checkpoint.
            writes (List[Tuple[str, Any]]): List of writes to store.
            task_id (str): Identifier for the task creating the writes.
        """
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"]["checkpoint_ns"]
        checkpoint_id = config["configurable"]["checkpoint_id"]
        query = (
            self.UPSERT_WRITES_SQL
            if all(w[0] in WRITES_IDX_MAP for w in writes)
            else self.INSERT_WRITES_SQL
        )
        with self.sync_cursor() as cur:
            cur.executemany(
                query,
                self._dump_writes(
                    thread_id, checkpoint_ns, checkpoint_id, task_id, writes
                ),
            )

    async def aput_writes(
        self, config: RunnableConfig, writes: List[Tuple[str | Any]], task_id: str
    ) -> None:
        """Store intermediate writes linked to a checkpoint.

        This method saves intermediate writes associated with a checkpoint to the Postgres database.

        Args:
            config (RunnableConfig): Configuration of the related checkpoint.
            writes (List[Tuple[str, Any]]): List of writes to store.
            task_id (str): Identifier for the task creating the writes.
        """
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"]["checkpoint_ns"]
        checkpoint_id = config["configurable"]["checkpoint_id"]
        query = (
            self.UPSERT_WRITES_SQL
            if all(w[0] in WRITES_IDX_MAP for w in writes)
            else self.INSERT_WRITES_SQL
        )
        async with self.async_cursor() as cur:
            await cur.executemany(
                query,
                self._dump_writes(
                    thread_id, checkpoint_ns, checkpoint_id, task_id, writes
                ),
            )

    def list(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> Iterator[CheckpointTuple]:
        """List checkpoints from the database.

        This method retrieves a list of checkpoint tuples from the Postgres database based
        on the provided config. The checkpoints are ordered by checkpoint ID in descending order (newest first).

        Args:
            config (RunnableConfig): The config to use for listing the checkpoints.
            filter (Dict[str, Any] | None): Additional filtering criteria for metadata. Defaults to None.
            before (RunnableConfig | None): If provided, only checkpoints before the specified checkpoint ID are returned. Defaults to None.
            limit (int | None): The maximum number of checkpoints to return. Defaults to None.

        Yields:
            Iterator[CheckpointTuple]: An iterator of checkpoint tuples.
        """
        where, param_values = search_where(config, filter, before, "postgres")
        query = self.SELECT_CHECKPOINTS_TEMPLATE.format(where=where)
        if limit:
            query += f" LIMIT {limit}"
        thread_id = config["configurable"]["thread_id"]

        with self.sync_cursor() as cur, self.get_sync_connection() as wconn:
            with wconn.cursor() as wcur:
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
                        self.SELECT_WRITES_SQL,
                        {
                            "thread_id": thread_id,
                            "checkpoint_ns": checkpoint_ns,
                            "checkpoint_id": checkpoint_id,
                        },
                    )
                    yield CheckpointTuple(
                        config={
                            "configurable": {
                                "thread_id": thread_id,
                                "checkpoint_ns": checkpoint_ns,
                                "checkpoint_id": checkpoint_id,
                            }
                        },
                        checkpoint=self.serde.loads(checkpoint),
                        metadata=self.serde.loads(metadata),
                        parent_config={
                            "configurable": {
                                "thread_id": thread_id,
                                "checkpoint_ns": checkpoint_ns,
                                "checkpoint_id": parent_checkpoint_id,
                            }
                        }
                        if parent_checkpoint_id
                        else None,
                        pending_writes=[
                            (task_id, channel, self.serde.loads(value))
                            for task_id, channel, value in wcur
                        ],
                    )

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        """List checkpoints from the database.

        This method retrieves a list of checkpoint tuples from the Postgres database based
        on the provided config. The checkpoints are ordered by checkpoint ID in descending order (newest first).

        Args:
            config (RunnableConfig): The config to use for listing the checkpoints.
            filter (Dict[str, Any] | None): Additional filtering criteria for metadata. Defaults to None.
            before (RunnableConfig | None): If provided, only checkpoints before the specified checkpoint ID are returned. Defaults to None.
            limit (int | None): The maximum number of checkpoints to return. Defaults to None.

        Yields:
            Iterator[CheckpointTuple]: An iterator of checkpoint tuples.
        """
        where, param_values = search_where(config, filter, before, "postgres")
        query = self.SELECT_CHECKPOINTS_TEMPLATE.format(where=where)
        if limit:
            query += f" LIMIT {limit}"
        thread_id = config["configurable"]["thread_id"]

        # TODO: Check that postgres will support two cursors at the same time and check if the async cursor is working
        async with self.async_cursor() as cur, self.get_async_connection() as wconn:
            async with wconn.cursor() as wcur:
                cur.execute(query, param_values)
                async for (
                    thread_id,
                    checkpoint_ns,
                    checkpoint_id,
                    parent_checkpoint_id,
                    checkpoint,
                    metadata,
                ) in cur:
                    wcur.execute(
                        self.SELECT_WRITES_SQL,
                        {
                            "thread_id": thread_id,
                            "checkpoint_ns": checkpoint_ns,
                            "checkpoint_id": checkpoint_id,
                        },
                    )
                    yield CheckpointTuple(
                        config={
                            "configurable": {
                                "thread_id": thread_id,
                                "checkpoint_ns": checkpoint_ns,
                                "checkpoint_id": checkpoint_id,
                            }
                        },
                        checkpoint=self.serde.loads(checkpoint),
                        metadata=self.serde.loads(metadata),
                        parent_config={
                            "configurable": {
                                "thread_id": thread_id,
                                "checkpoint_ns": checkpoint_ns,
                                "checkpoint_id": parent_checkpoint_id,
                            }
                        }
                        if parent_checkpoint_id
                        else None,
                        pending_writes=[
                            (task_id, channel, self.serde.loads(value))
                            async for task_id, channel, value in wcur
                        ],
                    )

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        """Get a checkpoint tuple from the database.

        This method retrieves a checkpoint tuple from the Postgres database based on the
        provided config. If the config contains a "checkpoint_id" key, the checkpoint with
        the matching thread ID and timestamp is retrieved. Otherwise, the latest checkpoint
        for the given thread ID is retrieved.

        Args:
            config (RunnableConfig): The config to use for retrieving the checkpoint.

        Returns:
            CheckpointTuple | None: The retrieved checkpoint tuple, or
                None if no matching checkpoint was found.
        """
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        with self.sync_cursor() as cur:
            # get the checkpoint requested or return the latest checkpoint
            if checkpoint_id := get_checkpoint_id(config):
                cur.execute(
                    self.SELECT_CHECKPOINT_SQL,
                    {
                        "thread_id": config["configurable"]["thread_id"],
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": checkpoint_id,
                    },
                )
            else:
                cur.execute(
                    self.SELECT_RECENT_CHECKPOINT_SQL,
                    {
                        "thread_id": config["configurable"]["thread_id"],
                        "checkpoint_ns": checkpoint_ns,
                    },
                )
            # if a checkpoint is found, return it
            try:
                value = cur.fetchone()
            except psycopg.ProgrammingError:
                return None
            if value:
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
                    self.SELECT_WRITES_SQL,
                    {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": checkpoint_id,
                    },
                )
                if metadata is not None:
                    metadata = cast(CheckpointMetadata, self.serde.loads(metadata))
                else:
                    metadata = {}
                return CheckpointTuple(
                    config=config,
                    checkpoint=cast(Checkpoint, self.serde.loads(checkpoint)),
                    metadata=metadata,
                    parent_config={
                        "configurable": {
                            "thread_id": thread_id,
                            "checkpoint_ns": checkpoint_ns,
                            "checkpoint_id": parent_checkpoint_id,
                        }
                    }
                    if parent_checkpoint_id
                    else None,
                    pending_writes=[
                        (task_id, channel, self.serde.loads(value))
                        for task_id, channel, value in cur
                    ],
                )
        return None

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        """Get a checkpoint tuple from the database.

        This method retrieves a checkpoint tuple from the Postgres database based on the
        provided config. If the config contains a "checkpoint_id" key, the checkpoint with
        the matching thread ID and timestamp is retrieved. Otherwise, the latest checkpoint
        for the given thread ID is retrieved.

        Args:
            config (RunnableConfig): The config to use for retrieving the checkpoint.

        Returns:
            CheckpointTuple | None: The retrieved checkpoint tuple, or
                None if no matching checkpoint was found.
        """
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        async with self.async_cursor() as cur:
            # get the checkpoint requested or return the latest checkpoint
            if checkpoint_id := get_checkpoint_id(config):
                await cur.execute(
                    self.SELECT_CHECKPOINT_SQL,
                    {
                        "thread_id": config["configurable"]["thread_id"],
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": checkpoint_id,
                    },
                )
            else:
                await cur.execute(
                    self.SELECT_RECENT_CHECKPOINT_SQL,
                    {
                        "thread_id": config["configurable"]["thread_id"],
                        "checkpoint_ns": checkpoint_ns,
                    },
                )
            # if a checkpoint is found, return it
            try:
                value = await cur.fetchone()
            except psycopg.ProgrammingError:
                return None
            if value:
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
                    self.SELECT_WRITES_SQL,
                    {
                        "thread_id": thread_id,
                        "checkpoint_ns": checkpoint_ns,
                        "checkpoint_id": checkpoint_id,
                    },
                )
                if metadata is not None:
                    metadata = cast(CheckpointMetadata, self.serde.loads(metadata))
                else:
                    metadata = {}
                return CheckpointTuple(
                    config=config,
                    checkpoint=cast(Checkpoint, self.serde.loads(checkpoint)),
                    metadata=metadata,
                    parent_config={
                        "configurable": {
                            "thread_id": thread_id,
                            "checkpoint_ns": checkpoint_ns,
                            "checkpoint_id": parent_checkpoint_id,
                        }
                    }
                    if parent_checkpoint_id
                    else None,
                    pending_writes=[
                        (task_id, channel, self.serde.loads(value))
                        for task_id, channel, value in await cur.fetchall()
                    ],
                )
        return None


class PostgresCheckpointer(PostgresSaver):
    serde = None

    def __init__(self, serializer: PostgresSerializer):
        super().__init__()
        self.serde = serializer
