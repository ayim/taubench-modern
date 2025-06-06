from psycopg.errors import ForeignKeyViolation, UniqueViolation
from psycopg.types.json import Jsonb
from structlog import get_logger

from agent_platform.core.storage import ScopedStorage
from agent_platform.server.storage.errors import (
    RecordAlreadyExistsError,
    ReferenceIntegrityError,
    ScopedStorageNotFoundError,
)
from agent_platform.server.storage.postgres.common import CommonMixin


class PostgresStorageScopedStorageMixin(CommonMixin):
    """
    Mixin providing PostgreSQL-based scoped storage operations.

    This mixin implements methods to create, retrieve, list, upsert, and delete
    scoped storage records from the Postgres database. It assumes that a working
    `_cursor()` (which yields an async psycopg cursor) and `_validate_uuid()`
    method (for validating UUID strings) are available from the inherited
    CommonMixin.
    """

    _logger = get_logger(__name__)

    async def create_scoped_storage(self, storage: ScopedStorage) -> None:
        """Insert a new scoped storage record."""
        self._validate_uuid(storage.storage_id)
        self._validate_uuid(storage.created_by_user_id)
        self._validate_uuid(storage.created_by_agent_id)
        self._validate_uuid(storage.created_by_thread_id)
        storage_dict = storage.model_dump()
        # Wrap the "storage" field in a Jsonb object so that psycopg
        # handles it properly.
        storage_dict["storage"] = Jsonb(storage_dict["storage"])
        try:
            async with self._cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO v2."scoped_storage" (
                        storage_id, created_at, updated_at,
                        created_by_user_id, created_by_agent_id, created_by_thread_id,
                        scope_type, storage
                    )
                    VALUES (
                        %(storage_id)s, %(created_at)s, %(updated_at)s,
                        %(created_by_user_id)s, %(created_by_agent_id)s,
                        %(created_by_thread_id)s, %(scope_type)s, %(storage)s
                    )
                    """,
                    storage_dict,
                )
        except ForeignKeyViolation as e:
            raise ReferenceIntegrityError(
                "Invalid foreign key reference updating scoped storage",
            ) from e
        except UniqueViolation as e:
            if "duplicate key value violates unique constraint" in str(e):
                raise RecordAlreadyExistsError(
                    f"Scoped storage {storage.storage_id} already exists",
                ) from e
            raise e
        except Exception:
            raise

    async def get_scoped_storage(self, storage_id: str) -> ScopedStorage:
        """Retrieve a scoped storage record by its ID."""
        self._validate_uuid(storage_id)
        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT *
                FROM v2."scoped_storage"
                WHERE storage_id = %(storage_id)s
                """,
                {"storage_id": storage_id},
            )
            row = await cur.fetchone()
        if not row:
            raise ScopedStorageNotFoundError(f"Scoped storage {storage_id} not found")
        storage_dict = dict(row)
        storage_dict = self._convert_scoped_storage_json_fields(storage_dict)
        return ScopedStorage.model_validate(storage_dict)

    async def list_scoped_storage(
        self,
        scope_type: str,
        scope_id: str,
    ) -> list[ScopedStorage]:
        """
        List all scoped storage records for a given scope type and scope identifier.
        """
        self._validate_uuid(scope_id)

        # Validate that scope_type is one of the expected values
        if scope_type not in ("user", "agent", "thread"):
            raise ValueError(f"Invalid scope_type: {scope_type}")

        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT *
                FROM v2."scoped_storage"
                WHERE %(scope_type_param)s = scope_type AND (
                   -- Bit tricky, we write it this way to avoid
                   -- building a dynamic SQL query.
                   (
                     %(scope_type_param)s = 'user'
                     AND created_by_user_id = %(scope_id)s
                   )
                   OR (
                     %(scope_type_param)s = 'agent'
                     AND created_by_agent_id = %(scope_id)s
                   )
                   OR (
                     %(scope_type_param)s = 'thread'
                     AND created_by_thread_id = %(scope_id)s
                   )
                )
                ORDER BY created_at
                """,
                {
                    "scope_type_param": scope_type,
                    "scope_id": scope_id,
                },
            )
            rows = await cur.fetchall()

        if not rows:
            return []
        return [
            ScopedStorage.model_validate(
                self._convert_scoped_storage_json_fields(dict(r)),
            )
            for r in rows
        ]

    async def upsert_scoped_storage(self, storage: ScopedStorage) -> None:
        """Insert or update a scoped storage record."""
        self._validate_uuid(storage.storage_id)
        self._validate_uuid(storage.created_by_user_id)
        self._validate_uuid(storage.created_by_agent_id)
        self._validate_uuid(storage.created_by_thread_id)
        storage_dict = storage.model_dump()
        # Wrap the storage field with Jsonb so that PostgreSQL stores it as JSONB.
        storage_dict["storage"] = Jsonb(storage_dict["storage"])
        try:
            async with self._cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO v2."scoped_storage" (
                        storage_id, created_at, updated_at,
                        created_by_user_id, created_by_agent_id, created_by_thread_id,
                        scope_type, storage
                    )
                    VALUES (
                        %(storage_id)s, %(created_at)s, %(updated_at)s,
                        %(created_by_user_id)s, %(created_by_agent_id)s,
                        %(created_by_thread_id)s, %(scope_type)s, %(storage)s
                    )
                    ON CONFLICT (storage_id) DO UPDATE SET
                        created_at = EXCLUDED.created_at,
                        updated_at = EXCLUDED.updated_at,
                        created_by_user_id = EXCLUDED.created_by_user_id,
                        created_by_agent_id = EXCLUDED.created_by_agent_id,
                        created_by_thread_id = EXCLUDED.created_by_thread_id,
                        scope_type = EXCLUDED.scope_type,
                        storage = EXCLUDED.storage
                    """,
                    storage_dict,
                )
                if cur.rowcount == 0:
                    self._logger.warning(
                        "Upsert scoped storage had no effect",
                        storage_id=storage_dict["storage_id"],
                    )
        except ForeignKeyViolation as e:
            raise ReferenceIntegrityError(
                "Invalid foreign key reference updating scoped storage",
            ) from e
        except UniqueViolation as e:
            if "duplicate key value violates unique constraint" in str(e):
                raise RecordAlreadyExistsError(
                    f"Scoped storage {storage.storage_id} already exists",
                ) from e
            raise e
        except Exception:
            raise

    async def delete_scoped_storage(self, storage_id: str) -> None:
        """
        Delete a scoped storage record.

        Raises:
            ScopedStorageNotFoundError: If no record with the given storage_id exists.
        """
        self._validate_uuid(storage_id)
        async with self._cursor() as cur:
            await cur.execute(
                """
                DELETE FROM v2."scoped_storage"
                WHERE storage_id = %(storage_id)s
                """,
                {"storage_id": storage_id},
            )
            if cur.rowcount == 0:
                raise ScopedStorageNotFoundError(
                    f"Scoped storage {storage_id} not found",
                )

    def _convert_scoped_storage_json_fields(self, storage_dict: dict) -> dict:
        """
        Convert JSON fields in a scoped storage record to Python objects if necessary.

        If the 'storage' field is still a string, this helper converts it
        to a Python object.
        """
        if "storage" in storage_dict and isinstance(storage_dict["storage"], str):
            import json

            storage_dict["storage"] = json.loads(storage_dict["storage"])
        return storage_dict
