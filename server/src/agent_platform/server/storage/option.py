from os import getenv
from typing import Final

from agent_platform.server.storage.base import BaseStorage
from agent_platform.server.storage.postgres import PostgresStorage
from agent_platform.server.storage.sqlite import SQLiteStorage


def initialize_storage() -> BaseStorage:
    db_type = getenv("S4_AGENT_SERVER_DB_TYPE", "sqlite")
    if db_type == "postgres":
        return PostgresStorage()
    elif db_type == "sqlite":
        return SQLiteStorage()
    else:
        raise ValueError(f"Unsupported DB type: {db_type}")

STORAGE: Final[BaseStorage] = initialize_storage()

def get_storage() -> BaseStorage:
    return STORAGE
