from datetime import datetime
from uuid import uuid4

from psycopg.errors import UniqueViolation

from agent_server_types_v2.user import User
from sema4ai_agent_server.storage.v2.errors_v2 import NoSystemUserError
from sema4ai_agent_server.storage.v2.postgres_v2.common import CommonMixin


class PostgresStorageUsersMixin(CommonMixin):

    async def get_system_user_id_v2(self) -> str:
        """Get the system user ID."""
        async with self._cursor() as cur:
            await cur.execute("SELECT user_id FROM v2.user WHERE sub LIKE 'tenant:%%:system:system_user'")
            if row := await cur.fetchone():
                # Str because we're getting back a UUID instance from psycopg
                return str(row["user_id"])
        raise NoSystemUserError()

    async def get_or_create_user_v2(self, sub: str) -> tuple[User, bool]:
        """Returns a tuple of the user and a boolean indicating whether the user was created."""
        async with self._cursor() as cur:
            await cur.execute("SELECT * FROM v2.user WHERE sub = %(sub)s", {"sub": sub})
            if row := await cur.fetchone():
                return User.from_dict(row), False

        # Not found: create
        user_id = str(uuid4())
        created_at = datetime.now()
        try:
            async with self._cursor() as cur:
                await cur.execute("""
                    INSERT INTO v2.user (user_id, sub, created_at) 
                    VALUES (%(user_id)s, %(sub)s, %(created_at)s)
                    RETURNING user_id, sub, created_at
                    """,
                    {"user_id": user_id, "sub": sub, "created_at": created_at},
                )
                row = await cur.fetchone()
                return User.from_dict(row), True
        except UniqueViolation as e:
            if "sub" in str(e):
                async with self._cursor() as cur:
                    await cur.execute("SELECT * FROM v2.user WHERE sub = %(sub)s", {"sub": sub})
                    if row := await cur.fetchone():
                        return User.from_dict(row), False


    async def delete_user_v2(self, user_id: str) -> None:
        """
        Delete a user by ID.
        """
        self._validate_uuid(user_id)
        async with self._cursor() as cur:
            await cur.execute("DELETE FROM v2.user WHERE user_id = %(user_id)s", {"user_id": user_id})

