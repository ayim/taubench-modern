from datetime import UTC, datetime

from psycopg.errors import UniqueViolation

from agent_platform.core.platforms.base import PlatformParameters
from agent_platform.server.storage.common import CommonMixin
from agent_platform.server.storage.errors import (
    PlatformConfigNotFoundError,
    PlatformConfigWithNameAlreadyExistsError,
    RecordAlreadyExistsError,
)
from agent_platform.server.storage.postgres.cursor import CursorMixin


class PostgresStoragePlatformConfigsMixin(CursorMixin, CommonMixin):
    """Mixin for PostgreSQL platform parameters operations."""

    async def create_platform_params(self, platform_params: PlatformParameters) -> None:
        """Create a new platform configuration."""
        # 1. Use the platform_id from the object (it has a default UUID)
        platform_params_id = platform_params.platform_id

        # 2. Encrypt the parameters
        encrypted_parameters = self._encrypt_config(platform_params.model_dump())

        # 3. Insert the platform params
        try:
            async with self._transaction() as cur:
                await cur.execute(
                    """
                    INSERT INTO v2.platform_params (
                        platform_params_id, name, enc_parameters
                    )
                    VALUES (
                        %s::uuid, %s, %s
                    )
                    """,
                    (
                        platform_params_id,
                        platform_params.name,
                        encrypted_parameters,
                    ),
                )
        except UniqueViolation as e:
            if "platform_params_pkey" in str(e):
                raise RecordAlreadyExistsError(
                    f"Platform params {platform_params_id} already exists",
                ) from e
            elif "idx_platform_params_name" in str(e):
                raise PlatformConfigWithNameAlreadyExistsError(
                    f"Platform params with name '{platform_params.name}' already exists",
                ) from e
            raise

    async def get_platform_params(self, platform_params_id: str) -> PlatformParameters:
        """Get a platform configuration by ID."""
        # 1. Validate the uuids
        self._validate_uuid(platform_params_id)

        async with self._cursor() as cur:
            # 2. Get the platform params
            await cur.execute(
                """
                SELECT platform_params_id, name, enc_parameters FROM v2.platform_params
                WHERE platform_params_id = %s::uuid
                """,
                (platform_params_id,),
            )

            # 3. No platform params found?
            if not (row := await cur.fetchone()):
                raise PlatformConfigNotFoundError(f"Platform params {platform_params_id} not found")

            # 4. Decrypt the enc_parameters and set platform_id to database ID
            params_data = self._decrypt_config(row["enc_parameters"])
            params_data["platform_id"] = str(row["platform_params_id"])
            return PlatformParameters.model_validate(params_data)

    async def list_platform_params(self) -> list[PlatformParameters]:
        """List all platform configurations."""
        async with self._cursor() as cur:
            # 2. Get all platform params for this user
            await cur.execute(
                """
                SELECT platform_params_id, name, enc_parameters FROM v2.platform_params
                ORDER BY created_at DESC
                """,
            )

            # 3. No platform params found?
            if not (rows := await cur.fetchall()):
                return []

            # 4. Return the platform params as a list with platform_id set to database ID
            result = []
            for row in rows:
                params_data = self._decrypt_config(row["enc_parameters"])
                params_data["platform_id"] = str(row["platform_params_id"])
                result.append(PlatformParameters.model_validate(params_data))
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
        now = datetime.now(UTC)
        encrypted_parameters = self._encrypt_config(platform_params.model_dump())

        # 3. Update the platform params with user access check
        try:
            async with self._transaction() as cur:
                await cur.execute(
                    """
                    UPDATE v2.platform_params
                    SET name = %s,
                        enc_parameters = %s,
                        updated_at = %s
                    WHERE platform_params_id = %s::uuid
                    """,
                    (
                        platform_params.name,
                        encrypted_parameters,
                        now,
                        platform_params_id,
                    ),
                )

                # 4. Check if update succeeded
                if cur.rowcount == 0:
                    raise PlatformConfigNotFoundError(
                        f"Platform params {platform_params_id} not found",
                    )
        except UniqueViolation as e:
            if "idx_platform_params_name" in str(e):
                raise PlatformConfigWithNameAlreadyExistsError(
                    f"Platform params with name '{platform_params.name}' already exists",
                ) from e
            raise

    async def delete_platform_params(self, platform_params_id: str) -> None:
        """Delete a platform configuration."""
        # 1. Validate the uuids
        self._validate_uuid(platform_params_id)

        async with self._transaction() as cur:
            # 2. Delete the platform params with user access check
            await cur.execute(
                """
                DELETE FROM v2.platform_params
                WHERE platform_params_id = %s::uuid
                """,
                (platform_params_id,),
            )

            # 3. Check if delete succeeded
            if cur.rowcount == 0:
                raise PlatformConfigNotFoundError(f"Platform params {platform_params_id} not found")
