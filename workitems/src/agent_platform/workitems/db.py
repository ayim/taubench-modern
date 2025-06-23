from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


class DatabaseManager:
    """Manages the database connection and session."""

    _engine: Engine | None = None
    _session_maker: sessionmaker | None = None

    def init_engine(self, dsn: str) -> None:
        if self._engine is None:
            self._engine = create_engine(dsn, echo=False)
            self._session_maker = sessionmaker(bind=self._engine)

    def get_engine(self) -> Engine:
        assert self._engine is not None, "engine not initialized"
        return self._engine

    @contextmanager
    def session(self) -> Generator[Session, None]:
        assert self._session_maker is not None, "engine not initialized"
        with self._session_maker() as session:
            yield session


instance = DatabaseManager()
