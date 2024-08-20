import os

from sema4ai_agent_server.file_manager.base import BaseFileManager
from sema4ai_agent_server.file_manager.cloud import CloudFileManager
from sema4ai_agent_server.file_manager.local import LocalFileManager

_file_manager = None


def get_file_manager() -> BaseFileManager:
    type_ = os.environ.get("S4_AGENT_SERVER_FILE_MANAGER_TYPE", "local")
    global _file_manager
    if _file_manager is None:
        if type_ == "local":
            _file_manager = LocalFileManager()
        elif type_ == "cloud":
            _file_manager = CloudFileManager()
        else:
            raise ValueError(f"Invalid file manager type: {type_}")
    return _file_manager
