from datetime import datetime
from uuid import uuid4

from aiosqlite import IntegrityError
from structlog import get_logger

from agent_platform.core.user import User
from agent_platform.server.storage.errors import NoSystemUserError
from agent_platform.server.storage.sqlite.common import CommonMixin


class SQLiteStorageUsersMixin(CommonMixin):
    """
    Mixin providing SQLite-based user operations.
    """

    _logger = get_logger(__name__)

    async def get_system_user_id(self) -> str:
        """
        Get the system user ID (sub like 'tenant:%:system:system_user'),
        or raise NoSystemUserError if none found.
        """
        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT user_id
                FROM v2_user
                WHERE sub LIKE 'tenant:%:system:system_user'
                LIMIT 1
                """,
            )
            row = await cur.fetchone()

        if not row:
            raise NoSystemUserError("No system user found")
        return str(row["user_id"])

    async def get_or_create_user(self, sub: str) -> tuple[User, bool]:
        """
        Look up a user by sub, or create them if not found.
        Return (User, created_bool).
        """
        async with self._cursor() as cur:
            await cur.execute("SELECT * FROM v2_user WHERE sub = :sub", {"sub": sub})
            row = await cur.fetchone()
        if row:
            return (User.model_validate(dict(row)), False)

        # Not found: create
        user_id = str(uuid4())
        created_at = datetime.now()
        try:
            async with self._cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO v2_user (user_id, sub, created_at)
                    VALUES (:user_id, :sub, :created_at)
                    """,
                    {"user_id": user_id, "sub": sub, "created_at": created_at},
                )
        except IntegrityError as e:
            # We force users to be unique by sub as well, so if we get an error,
            # it means the user already exists (and we can find the one with
            # the same sub).
            if "UNIQUE constraint failed: v2_user.sub" in str(e):
                async with self._cursor() as cur:
                    await cur.execute(
                        "SELECT * FROM v2_user WHERE sub = :sub",
                        {"sub": sub},
                    )
                    row = await cur.fetchone()
                    if row:
                        return (User.model_validate(dict(row)), False)

        # Fetch the newly created user
        async with self._cursor() as cur:
            await cur.execute(
                "SELECT * FROM v2_user WHERE user_id = :user_id",
                {"user_id": user_id},
            )
            new_row = await cur.fetchone()

        return (User.model_validate(dict(new_row)), True)

    async def delete_user(self, user_id: str) -> None:
        """
        Delete a user by ID.
        """
        self._validate_uuid(user_id)
        async with self._cursor() as cur:
            await cur.execute(
                "DELETE FROM v2_user WHERE user_id = :user_id",
                {"user_id": user_id},
            )
