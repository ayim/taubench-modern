from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


class DatabaseManager:
    """Manages the database connection and session."""

    def __init__(self) -> None:
        self._engine: AsyncEngine | None = None
        self._session_maker: async_sessionmaker | None = None

    def init_engine(self, dsn: str) -> None:
        if self._engine is None:
            self._engine = create_async_engine(dsn, echo=False)
            self._session_maker = async_sessionmaker(
                bind=self._engine, expire_on_commit=False, autobegin=False
            )

    def get_engine(self) -> AsyncEngine:
        assert self._engine is not None, "engine not initialized"
        return self._engine

    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        assert self._session_maker is not None, "engine not initialized"
        async with self._session_maker() as session:
            yield session

    @asynccontextmanager
    async def begin(self) -> AsyncGenerator[AsyncSession, None]:
        """Helper function for one-off transactions."""
        assert self._session_maker is not None, "engine not initialized"

        async with self._session_maker.begin() as session:
            yield session


instance = DatabaseManager()
