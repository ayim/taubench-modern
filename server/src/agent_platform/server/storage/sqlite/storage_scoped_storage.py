import json
from sqlite3 import IntegrityError

from structlog import get_logger

from agent_platform.core.storage import ScopedStorage
from agent_platform.server.storage.errors import (
    RecordAlreadyExistsError,
    ReferenceIntegrityError,
    ScopedStorageNotFoundError,
)
from agent_platform.server.storage.sqlite.common import CommonMixin


class SQLiteStorageScopedStorageMixin(CommonMixin):
    """
    Mixin providing SQLite-based scoped storage operations.
    Assumes that helper methods such as `_cursor()` and
    `_validate_uuid()` are available.
    """
    _logger = get_logger(__name__)

    # -------------------------------------------------------------------------
    # Scoped Storage
    # -------------------------------------------------------------------------
    async def create_scoped_storage(self, storage: ScopedStorage) -> None:
        """Insert a new scoped storage record."""
        self._validate_uuid(storage.storage_id)
        self._validate_uuid(storage.created_by_user_id)
        self._validate_uuid(storage.created_by_agent_id)
        self._validate_uuid(storage.created_by_thread_id)
        storage_dict = storage.model_dump()
        # Convert the storage field (which is a dict) to a JSON string.
        storage_dict["storage"] = json.dumps(storage_dict["storage"])
        try:
            async with self._cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO v2_scoped_storage (
                        storage_id, created_at, updated_at,
                        created_by_user_id, created_by_agent_id, created_by_thread_id,
                        scope_type, storage
                    )
                    VALUES (
                        :storage_id, :created_at, :updated_at,
                        :created_by_user_id, :created_by_agent_id,
                        :created_by_thread_id, :scope_type, :storage
                    )
                    """,
                    storage_dict,
                )
        except IntegrityError as e:
            if "UNIQUE constraint failed: v2_scoped_storage.storage_id" in str(e):
                raise RecordAlreadyExistsError(
                    f"Scoped storage {storage.storage_id} already exists",
                ) from e
            raise ReferenceIntegrityError(
                "Invalid foreign key reference updating scoped storage",
            ) from e

    async def get_scoped_storage(self, storage_id: str) -> ScopedStorage:
        """Retrieve a scoped storage record by its ID."""
        self._validate_uuid(storage_id)
        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT *
                FROM v2_scoped_storage
                WHERE storage_id = :storage_id
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
        self, scope_type: str, scope_id: str,
    ) -> list[ScopedStorage]:
        """
        List all scoped storage records for a given scope type and scope identifier.
        """
        self._validate_uuid(scope_id)

        # Optionally validate the scope_type before running the query
        if scope_type not in ("user", "agent", "thread"):
            raise ValueError(f"Invalid scope_type: {scope_type}")

        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT *
                FROM v2_scoped_storage
                WHERE :scope_type = scope_type AND (
                    -- Bit tricky, we write it this way to
                    -- avoid building a dynamic SQL query.
                    (:scope_type = 'user' AND created_by_user_id = :scope_id)
                    OR (:scope_type = 'agent' AND created_by_agent_id = :scope_id)
                    OR (:scope_type = 'thread' AND created_by_thread_id = :scope_id)
                )
                ORDER BY created_at
                """,
                {"scope_type": scope_type, "scope_id": scope_id},
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
        storage_dict["storage"] = json.dumps(storage_dict["storage"])
        try:
            async with self._cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO v2_scoped_storage (
                        storage_id, created_at, updated_at,
                        created_by_user_id, created_by_agent_id, created_by_thread_id,
                        scope_type, storage
                    )
                    VALUES (
                        :storage_id, :created_at, :updated_at,
                        :created_by_user_id, :created_by_agent_id,
                        :created_by_thread_id, :scope_type, :storage
                    )
                    ON CONFLICT(storage_id) DO UPDATE SET
                        created_at = excluded.created_at,
                        updated_at = excluded.updated_at,
                        created_by_user_id = excluded.created_by_user_id,
                        created_by_agent_id = excluded.created_by_agent_id,
                        created_by_thread_id = excluded.created_by_thread_id,
                        scope_type = excluded.scope_type,
                        storage = excluded.storage
                    """,
                    storage_dict,
                )
                if cur.rowcount == 0:
                    self._logger.warning(
                        "Upsert scoped storage had no effect",
                        storage_id=storage_dict["storage_id"],
                    )
        except IntegrityError as e:
            if "UNIQUE constraint failed: v2_scoped_storage.storage_id" in str(e):
                raise RecordAlreadyExistsError(
                    f"Scoped storage {storage.storage_id} already exists",
                ) from e
            raise ReferenceIntegrityError(
                "Invalid foreign key reference updating scoped storage",
            ) from e

    async def delete_scoped_storage(self, storage_id: str) -> None:
        """Delete a scoped storage record.
        Raises ScopedStorageNotFoundError if not found."""
        self._validate_uuid(storage_id)
        async with self._cursor() as cur:
            await cur.execute(
                """
                DELETE FROM v2_scoped_storage
                WHERE storage_id = :storage_id
                """,
                {"storage_id": storage_id},
            )
            if cur.rowcount == 0:
                raise ScopedStorageNotFoundError(
                    f"Scoped storage {storage_id} not found",
                )

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def _convert_scoped_storage_json_fields(self, storage_dict: dict) -> dict:
        """Convert JSON string fields in a scoped storage record to Python objects."""
        if storage_dict.get("storage") is not None:
            storage_dict["storage"] = json.loads(storage_dict["storage"])
        else:
            storage_dict["storage"] = {}
        return storage_dict
