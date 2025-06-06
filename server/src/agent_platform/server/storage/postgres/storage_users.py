from datetime import UTC, datetime
from uuid import uuid4

from psycopg.errors import UniqueViolation

from agent_platform.core.user import User
from agent_platform.server.storage.errors import NoSystemUserError
from agent_platform.server.storage.postgres.common import CommonMixin


class PostgresStorageUsersMixin(CommonMixin):
    async def get_system_user_id(self) -> str:
        """Get the system user ID."""
        async with self._cursor() as cur:
            await cur.execute("""
                SELECT user_id FROM v2.user
                WHERE sub LIKE 'tenant:%%:system:system_user'
            """)
            if row := await cur.fetchone():
                # Str because we're getting back a UUID instance from psycopg
                return str(dict(row)["user_id"])
        raise NoSystemUserError()

    async def get_or_create_user(self, sub: str) -> tuple[User, bool]:
        """Returns a tuple of the user and a boolean
        indicating whether the user was created."""
        async with self._cursor() as cur:
            await cur.execute("SELECT * FROM v2.user WHERE sub = %(sub)s", {"sub": sub})
            if row := await cur.fetchone():
                return User.model_validate(dict(row)), False

        # Not found: create
        user_id = str(uuid4())
        created_at = datetime.now(UTC)
        try:
            async with self._cursor() as cur:
                await cur.execute(
                    """
                    INSERT INTO v2.user (user_id, sub, created_at)
                    VALUES (%(user_id)s, %(sub)s, %(created_at)s)
                    RETURNING user_id, sub, created_at
                    """,
                    {"user_id": user_id, "sub": sub, "created_at": created_at},
                )
                row = await cur.fetchone()
                if row is None:
                    raise ValueError("New row not found")
                return User.model_validate(dict(row)), True
        except UniqueViolation as e:
            if "sub" in str(e):
                async with self._cursor() as cur:
                    await cur.execute(
                        "SELECT * FROM v2.user WHERE sub = %(sub)s",
                        {"sub": sub},
                    )
                    if row := await cur.fetchone():
                        return User.model_validate(dict(row)), False
            raise e

    async def delete_user(self, user_id: str) -> None:
        """
        Delete a user by ID.
        """
        self._validate_uuid(user_id)
        async with self._cursor() as cur:
            await cur.execute(
                "DELETE FROM v2.user WHERE user_id = %(user_id)s",
                {"user_id": user_id},
            )
