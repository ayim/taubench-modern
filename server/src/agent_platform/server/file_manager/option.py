from os import getenv
from typing import Final

from agent_platform.server.file_manager.base import BaseFileManager
from agent_platform.server.file_manager.cloud import CloudFileManager
from agent_platform.server.file_manager.local import LocalFileManager


def initialize_file_manager() -> BaseFileManager:
    type_ = getenv("S4_AGENT_SERVER_FILE_MANAGER_TYPE", "local")
    if type_ == "local":
        return LocalFileManager()
    elif type_ == "cloud":
        return CloudFileManager()
    else:
        raise ValueError(f"Invalid file manager type: {type_}")

FILE_MANAGER: Final[BaseFileManager] = initialize_file_manager()

def get_file_manager() -> BaseFileManager:
    return FILE_MANAGER
