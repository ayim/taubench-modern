from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb

from agent_platform.core.memory import Memory
from agent_platform.server.storage.errors import (
    MemoryNotFoundError,
    RecordAlreadyExistsError,
)
from agent_platform.server.storage.postgres.common import CommonMixin


class PostgresStorageMemoriesMixin(CommonMixin):
    """
    Mixin providing PostgreSQL-based memory operations.

    This mixin implements methods to create, retrieve, list, upsert,
    and delete memory records in the Postgres database. It assumes that
    a working `_cursor()` (which yields an async psycopg cursor) and
    a `_validate_uuid()` method (for validating UUID strings) are available
    via the inherited CommonMixin.

    The implementation uses Postgres's native JSONB type (via psycopg's
    Jsonb wrapper) to store JSON data.
    """

    async def create_memory(self, memory: Memory) -> None:
        """Insert a new memory record into the database."""
        # Validate that memory.memory_id is a valid UUID string.
        self._validate_uuid(memory.memory_id)
        memory_dict = memory.model_dump()
        # Convert the JSONable fields into Jsonb objects for proper Postgres handling.
        memory_dict["metadata"] = Jsonb(memory_dict["metadata"])
        memory_dict["tags"] = Jsonb(memory_dict["tags"])
        memory_dict["refs"] = Jsonb(memory_dict["refs"])

        try:
            async with self._cursor() as cur:
                await cur.execute(
                    """
                INSERT INTO v2."memory" (
                    memory_id, original_text, contextualized_text,
                    created_at, updated_at, relevant_until_timestamp,
                    relevant_after_timestamp, scope, metadata,
                    tags, refs, weight, embedded, embedding_id
                )
                VALUES (
                    %(memory_id)s, %(original_text)s, %(contextualized_text)s,
                    %(created_at)s, %(updated_at)s, %(relevant_until_timestamp)s,
                    %(relevant_after_timestamp)s, %(scope)s, %(metadata)s,
                    %(tags)s, %(refs)s, %(weight)s, %(embedded)s, %(embedding_id)s
                )
                """,
                    memory_dict,
                )
        except UniqueViolation as e:
            if "duplicate key value violates unique constraint" in str(e):
                raise RecordAlreadyExistsError(
                    f"Memory {memory.memory_id} already exists",
                ) from e
            raise e
        except Exception:
            raise

    async def get_memory(self, memory_id: str) -> Memory:
        """Retrieve a memory record by its ID."""
        self._validate_uuid(memory_id)
        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT *
                FROM v2."memory"
                WHERE memory_id = %(memory_id)s
                """,
                {"memory_id": memory_id},
            )
            row = await cur.fetchone()
        if not row:
            raise MemoryNotFoundError(f"Memory {memory_id} not found")

        # In psycopg with a dict_row factory, JSONB columns are
        # usually already converted.
        memory_dict = dict(row)
        memory_dict = self._convert_memory_json_fields(memory_dict)
        return Memory.model_validate(memory_dict)

    async def list_memories(self, scope: str, scope_id: str) -> list[Memory]:
        """
        List all memory records for a given scope and scope identifier.

        This implementation assumes that each memory's metadata contains
        a key "scope_id" (as a string) that identifies the record's owner
        within that scope.
        """
        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT *
                FROM v2."memory"
                WHERE scope = %(scope)s
                  AND (metadata ->> 'scope_id') = %(scope_id)s
                ORDER BY created_at
                """,
                {"scope": scope, "scope_id": scope_id},
            )
            rows = await cur.fetchall()

        memories = []
        for row in rows:
            memory_dict = dict(row)
            memory_dict = self._convert_memory_json_fields(memory_dict)
            memories.append(Memory.model_validate(memory_dict))
        return memories

    async def upsert_memory(self, memory: Memory) -> None:
        """Insert or update a memory record in the database."""
        self._validate_uuid(memory.memory_id)
        memory_dict = memory.model_dump()
        # Wrap the JSON fields with Jsonb so that psycopg handles them correctly.
        memory_dict["metadata"] = Jsonb(memory_dict["metadata"])
        memory_dict["tags"] = Jsonb(memory_dict["tags"])
        memory_dict["refs"] = Jsonb(memory_dict["refs"])

        try:
            async with self._cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO v2."memory" (
                        memory_id, original_text, contextualized_text,
                        created_at, updated_at, relevant_until_timestamp,
                        relevant_after_timestamp, scope, metadata,
                        tags, refs, weight, embedded, embedding_id
                    )
                    VALUES (
                        %(memory_id)s, %(original_text)s, %(contextualized_text)s,
                        %(created_at)s, %(updated_at)s, %(relevant_until_timestamp)s,
                        %(relevant_after_timestamp)s, %(scope)s, %(metadata)s,
                        %(tags)s, %(refs)s, %(weight)s, %(embedded)s, %(embedding_id)s
                    )
                    ON CONFLICT (memory_id) DO UPDATE SET
                        original_text = EXCLUDED.original_text,
                        contextualized_text = EXCLUDED.contextualized_text,
                        updated_at = EXCLUDED.updated_at,
                        relevant_until_timestamp = EXCLUDED.relevant_until_timestamp,
                        relevant_after_timestamp = EXCLUDED.relevant_after_timestamp,
                        scope = EXCLUDED.scope,
                        metadata = EXCLUDED.metadata,
                        tags = EXCLUDED.tags,
                        refs = EXCLUDED.refs,
                        weight = EXCLUDED.weight,
                        embedded = EXCLUDED.embedded,
                        embedding_id = EXCLUDED.embedding_id
                    """,
                    memory_dict,
                )
        except UniqueViolation as e:
            if "duplicate key value violates unique constraint" in str(e):
                raise RecordAlreadyExistsError(
                    f"Memory {memory.memory_id} already exists",
                ) from e
            raise e
        except Exception:
            raise

    async def delete_memory(self, memory_id: str) -> None:
        """
        Delete a memory record from the database.

        Raises:
            MemoryNotFoundError: if no record with the given memory_id exists.
        """
        self._validate_uuid(memory_id)
        async with self._cursor() as cur:
            await cur.execute(
                """
                DELETE FROM v2."memory"
                WHERE memory_id = %(memory_id)s
                """,
                {"memory_id": memory_id},
            )
            if cur.rowcount == 0:
                raise MemoryNotFoundError(f"Memory {memory_id} not found")

    def _convert_memory_json_fields(self, memory_dict: dict) -> dict:
        """
        Convert JSON fields in the memory record to Python objects.

        In PostgreSQL with psycopg and a dict_row factory, JSONB columns are
        normally returned as Python objects. However, if any field is still a
        string, attempt to decode it.
        """
        for field in ["metadata", "tags", "refs"]:
            if field in memory_dict and isinstance(memory_dict[field], str):
                import json

                memory_dict[field] = json.loads(memory_dict[field])
        return memory_dict
