import json
from datetime import UTC, datetime
from sqlite3 import IntegrityError

from structlog import get_logger

from agent_platform.core.platforms.base import PlatformParameters
from agent_platform.server.storage.errors import (
    PlatformConfigNotFoundError,
    PlatformConfigWithNameAlreadyExistsError,
    RecordAlreadyExistsError,
)
from agent_platform.server.storage.sqlite.common import CommonMixin


class SQLiteStoragePlatformConfigsMixin(CommonMixin):
    """Mixin providing SQLite-based platform parameters operations."""

    _logger = get_logger(__name__)

    # -------------------------------------------------------------------------
    # Platform Parameters
    # -------------------------------------------------------------------------
    async def create_platform_params(
        self,
        platform_params: PlatformParameters,
    ) -> None:
        """Create a new platform configuration."""
        # 1. Use the platform_id from the object (it has a default UUID)
        platform_params_id = platform_params.platform_id

        # 2. Convert the entire parameters object to JSON
        parameters_json = json.dumps(platform_params.model_dump())

        # 3. Insert the platform params
        try:
            async with self._cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO v2_platform_params (
                        platform_params_id, name, parameters
                    )
                    VALUES (
                        ?, ?, ?
                    )
                    """,
                    (platform_params_id, platform_params.name, parameters_json),
                )
        except IntegrityError as e:
            if "UNIQUE constraint failed: v2_platform_params.platform_params_id" in str(e):
                raise RecordAlreadyExistsError(
                    f"Platform params {platform_params_id} already exists",
                ) from e
            elif "UNIQUE constraint failed: v2_platform_params.name" in str(e):
                raise PlatformConfigWithNameAlreadyExistsError(
                    f"Platform params with name '{platform_params.name}' already exists",
                ) from e
            raise

    async def get_platform_params(
        self,
        platform_params_id: str,
    ) -> PlatformParameters:
        """Get a platform configuration by ID."""
        # 1. Validate the uuids
        self._validate_uuid(platform_params_id)

        async with self._cursor() as cur:
            # 2. Get the platform params
            await cur.execute(
                """
                SELECT platform_params_id, name, parameters FROM v2_platform_params
                WHERE platform_params_id = ?
                """,
                (platform_params_id,),
            )

            # 3. No platform params found?
            if not (row := await cur.fetchone()):
                raise PlatformConfigNotFoundError(f"Platform params {platform_params_id} not found")

            # 4. Parse JSON data, set platform_id to database ID, and return the platform params
            parameters_data = json.loads(row[2])
            parameters_data["platform_id"] = row[0]  # platform_params_id
            return PlatformParameters.model_validate(parameters_data)

    async def list_platform_params(self) -> list[PlatformParameters]:
        """List all platform configurations."""
        async with self._cursor() as cur:
            # 2. Get all platform params for this user
            await cur.execute(
                """
                SELECT platform_params_id, name, parameters FROM v2_platform_params
                ORDER BY created_at DESC
                """,
            )

            # 3. No platform params found?
            if not (rows := await cur.fetchall()):
                return []

            # 4. Parse JSON data, set platform_id to database ID,
            # and return the platform params as a list
            result = []
            for row in rows:
                parameters_data = json.loads(row[2])
                parameters_data["platform_id"] = row[0]  # platform_params_id
                result.append(PlatformParameters.model_validate(parameters_data))
            return result

    async def update_platform_params(
        self,
        platform_params_id: str,
        platform_params: PlatformParameters,
    ) -> None:
        """Update a platform configuration."""
        # 1. Validate the uuids
        self._validate_uuid(platform_params_id)

        # 2. Prepare the data
        now = datetime.now(UTC).isoformat()
        parameters_json = json.dumps(platform_params.model_dump())

        # 3. Update the platform params with user access check
        try:
            async with self._cursor() as cur:
                await cur.execute(
                    """
                    UPDATE v2_platform_params
                    SET name = ?,
                        parameters = ?,
                        updated_at = ?
                    WHERE platform_params_id = ?
                    """,
                    (
                        platform_params.name,
                        parameters_json,
                        now,
                        platform_params_id,
                    ),
                )

                # 4. Check if update succeeded
                if cur.rowcount == 0:
                    raise PlatformConfigNotFoundError(
                        f"Platform params {platform_params_id} not found",
                    )
        except IntegrityError as e:
            if "UNIQUE constraint failed: v2_platform_params.name" in str(e):
                raise PlatformConfigWithNameAlreadyExistsError(
                    f"Platform params with name '{platform_params.name}' already exists",
                ) from e
            raise

    async def delete_platform_params(self, platform_params_id: str) -> None:
        """Delete a platform configuration."""
        # 1. Validate the uuids
        self._validate_uuid(platform_params_id)

        async with self._cursor() as cur:
            # 2. Delete the platform params with user access check
            await cur.execute(
                """
                DELETE FROM v2_platform_params
                WHERE platform_params_id = ?
                """,
                (platform_params_id,),
            )

            # 3. Check if delete succeeded
            if cur.rowcount == 0:
                raise PlatformConfigNotFoundError(f"Platform params {platform_params_id} not found")
