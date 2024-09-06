import os
from typing import Callable, Dict, Final

from langgraph.checkpoint import BaseCheckpointSaver


def get_postgres_checkpointer() -> BaseCheckpointSaver:
    from sema4ai_agent_server.storage.postgres_checkpointer import (
        PicklePostgresSerializer,
        PostgresCheckpointer,
    )

    return PostgresCheckpointer(serializer=PicklePostgresSerializer())


def get_sqlite_checkpointer() -> BaseCheckpointSaver:
    from sema4ai_agent_server.storage.sqlite_checkpointer import SQLiteCheckpoint

    return SQLiteCheckpoint()


CHECKPOINTER_TYPES: Final[Dict[str, Callable[[], BaseCheckpointSaver]]] = {
    "postgres": get_postgres_checkpointer,
    "sqlite": get_sqlite_checkpointer,
}


def initialize_checkpointer() -> BaseCheckpointSaver:
    db_type = os.environ.get("S4_AGENT_SERVER_DB_TYPE", "sqlite")
    checkpointer_func = CHECKPOINTER_TYPES.get(db_type)
    if checkpointer_func is None:
        raise ValueError(f"Invalid storage type: {db_type}")
    return checkpointer_func()


CHECKPOINTER: Final[BaseCheckpointSaver] = initialize_checkpointer()


def get_checkpointer() -> BaseCheckpointSaver:
    return CHECKPOINTER
