import os
from typing import Callable, Dict, Final

from sema4ai_agent_server.storage import BaseStorage


def get_postgres_storage() -> BaseStorage:
    from sema4ai_agent_server.storage.postgres import PostgresStorage

    return PostgresStorage()


def get_sqlite_storage() -> BaseStorage:
    from sema4ai_agent_server.storage.sqlite import SqliteStorage

    return SqliteStorage()


STORAGE_TYPES: Final[Dict[str, Callable[[], BaseStorage]]] = {
    "postgres": get_postgres_storage,
    "sqlite": get_sqlite_storage,
}


def initialize_storage() -> BaseStorage:
    db_type = os.environ.get("S4_AGENT_SERVER_DB_TYPE", "sqlite")
    storage_func = STORAGE_TYPES.get(db_type)
    if storage_func is None:
        raise ValueError(f"Invalid storage type: {db_type}")
    return storage_func()


STORAGE: Final[BaseStorage] = initialize_storage()


def get_storage() -> BaseStorage:
    return STORAGE
