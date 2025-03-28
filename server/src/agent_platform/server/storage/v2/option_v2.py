from os import getenv
from typing import Final

from sema4ai_agent_server.storage.v2.base_v2 import BaseStorageV2
from sema4ai_agent_server.storage.v2.postgres_v2 import PostgresStorageV2
from sema4ai_agent_server.storage.v2.sqlite_v2 import SQLiteStorageV2


def initialize_storage_v2() -> BaseStorageV2:
    db_type = getenv("S4_AGENT_SERVER_DB_TYPE", "sqlite")
    if db_type == "postgres":
        return PostgresStorageV2()
    elif db_type == "sqlite":
        return SQLiteStorageV2()
    else:
        raise ValueError(f"Unsupported DB type: {db_type}")

STORAGE_V2: Final[BaseStorageV2] = initialize_storage_v2()

def get_storage_v2() -> BaseStorageV2:
    return STORAGE_V2
