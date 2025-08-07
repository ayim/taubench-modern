import json

from aiosqlite import IntegrityError
from structlog import get_logger

from agent_platform.core.memory import Memory
from agent_platform.server.storage.common import CommonMixin
from agent_platform.server.storage.errors import (
    MemoryNotFoundError,
    RecordAlreadyExistsError,
)
from agent_platform.server.storage.sqlite.cursor import CursorMixin


class SQLiteStorageMemoriesMixin(CursorMixin, CommonMixin):
    """
    Mixin providing SQLite-based memory operations.
    Assumes that helper methods such as `_cursor()` and
    `_validate_uuid()` are available.
    """

    _logger = get_logger(__name__)

    async def create_memory(self, memory: Memory) -> None:
        """Insert a new memory record."""
        self._validate_uuid(memory.memory_id)
        memory_dict = memory.model_dump()
        # Convert JSONable fields to JSON strings
        memory_dict["metadata"] = json.dumps(memory_dict["metadata"])
        memory_dict["tags"] = json.dumps(memory_dict["tags"])
        memory_dict["refs"] = json.dumps(memory_dict["refs"])

        try:
            async with self._cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO v2_memory (
                        memory_id, original_text, contextualized_text,
                        created_at, updated_at, relevant_until_timestamp,
                        relevant_after_timestamp, scope, metadata,
                        tags, refs, weight, embedded, embedding_id
                    )
                    VALUES (
                        :memory_id, :original_text, :contextualized_text,
                        :created_at, :updated_at, :relevant_until_timestamp,
                        :relevant_after_timestamp, :scope, :metadata,
                        :tags, :refs, :weight, :embedded, :embedding_id
                    )
                    """,
                    memory_dict,
                )
        except IntegrityError as e:
            if "UNIQUE constraint failed: v2_memory.memory_id" in str(e):
                raise RecordAlreadyExistsError(
                    f"Memory {memory.memory_id} already exists",
                ) from e
            raise

    async def get_memory(self, memory_id: str) -> Memory:
        """Retrieve a memory record by its ID."""
        self._validate_uuid(memory_id)
        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT *
                FROM v2_memory
                WHERE memory_id = :memory_id
                """,
                {"memory_id": memory_id},
            )
            row = await cur.fetchone()
        if not row:
            raise MemoryNotFoundError(f"Memory {memory_id} not found")
        memory_dict = dict(row)
        memory_dict = self._convert_memory_json_fields(memory_dict)
        return Memory.model_validate(memory_dict)

    async def list_memories(self, scope: str, scope_id: str) -> list[Memory]:
        """
        List all memory records for a given scope and scope identifier.
        This implementation assumes that the memory's metadata stores the 'scope_id'
        (using JSON functions to extract it).
        """
        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT *
                FROM v2_memory
                WHERE scope = :scope
                  AND json_extract(metadata, '$.scope_id') = :scope_id
                ORDER BY created_at
                """,
                {"scope": scope, "scope_id": scope_id},
            )
            rows = await cur.fetchall()
        if not rows:
            return []
        memories = []
        for row in rows:
            memory_dict = dict(row)
            memory_dict = self._convert_memory_json_fields(memory_dict)
            memories.append(Memory.model_validate(memory_dict))
        return memories

    async def upsert_memory(self, memory: Memory) -> None:
        """Insert or update a memory record."""
        self._validate_uuid(memory.memory_id)
        memory_dict = memory.model_dump()
        memory_dict["metadata"] = json.dumps(memory_dict["metadata"])
        memory_dict["tags"] = json.dumps(memory_dict["tags"])
        memory_dict["refs"] = json.dumps(memory_dict["refs"])

        async with self._cursor() as cur:
            await cur.execute(
                """
                INSERT INTO v2_memory (
                    memory_id, original_text, contextualized_text,
                    created_at, updated_at, relevant_until_timestamp,
                    relevant_after_timestamp, scope, metadata,
                    tags, refs, weight, embedded, embedding_id
                )
                VALUES (
                    :memory_id, :original_text, :contextualized_text,
                    :created_at, :updated_at, :relevant_until_timestamp,
                    :relevant_after_timestamp, :scope, :metadata,
                    :tags, :refs, :weight, :embedded, :embedding_id
                )
                ON CONFLICT(memory_id) DO UPDATE SET
                    original_text = excluded.original_text,
                    contextualized_text = excluded.contextualized_text,
                    updated_at = excluded.updated_at,
                    relevant_until_timestamp = excluded.relevant_until_timestamp,
                    relevant_after_timestamp = excluded.relevant_after_timestamp,
                    scope = excluded.scope,
                    metadata = excluded.metadata,
                    tags = excluded.tags,
                    refs = excluded.refs,
                    weight = excluded.weight,
                    embedded = excluded.embedded,
                    embedding_id = excluded.embedding_id
                """,
                memory_dict,
            )
            if cur.rowcount == 0:
                self._logger.warning(
                    "Upsert memory had no effect",
                    memory_id=memory_dict["memory_id"],
                )

    async def delete_memory(self, memory_id: str) -> None:
        """Delete a memory record. Raises MemoryNotFoundError if not found."""
        self._validate_uuid(memory_id)
        async with self._cursor() as cur:
            await cur.execute(
                """
                DELETE FROM v2_memory
                WHERE memory_id = :memory_id
                """,
                {"memory_id": memory_id},
            )
            if cur.rowcount == 0:
                raise MemoryNotFoundError(f"Memory {memory_id} not found")

    def _convert_memory_json_fields(self, memory_dict: dict) -> dict:
        """Convert JSON string fields in a memory record to Python objects."""
        for field in ["metadata", "tags", "refs"]:
            if memory_dict.get(field) is not None:
                memory_dict[field] = json.loads(memory_dict[field])
            else:
                # For metadata we return an empty dict, for tags/refs an empty list
                memory_dict[field] = {} if field == "metadata" else []
        return memory_dict
