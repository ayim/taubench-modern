import os

from sema4ai_agent_server.file_manager.v2.base_v2 import BaseFileManagerV2
from sema4ai_agent_server.file_manager.v2.cloud_v2 import CloudFileManagerV2
from sema4ai_agent_server.file_manager.v2.local_v2 import LocalFileManagerV2

_file_manager = None


def get_file_manager_v2() -> BaseFileManagerV2:
    type_ = os.environ.get("S4_AGENT_SERVER_FILE_MANAGER_TYPE", "local")
    global _file_manager
    if _file_manager is None:
        if type_ == "local":
            _file_manager = LocalFileManagerV2()
        elif type_ == "cloud":
            _file_manager = CloudFileManagerV2()
        else:
            raise ValueError(f"Invalid file manager type: {type_}")
    return _file_manager
