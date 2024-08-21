import os

from sema4ai_agent_server.file_manager.base import BaseFileManager
from sema4ai_agent_server.file_manager.cloud import CloudFileManager
from sema4ai_agent_server.file_manager.local import LocalFileManager
from sema4ai_agent_server.schema import MODEL
from sema4ai_agent_server.storage.embed import get_vector_store

type_ = os.environ.get("S4_AGENT_SERVER_FILE_MANAGER_TYPE", "local")


def get_file_manager(model: MODEL) -> BaseFileManager:
    vectorstore = get_vector_store(model)
    if type_ == "local":
        return LocalFileManager(vectorstore)
    elif type_ == "cloud":
        return CloudFileManager(vectorstore)
    else:
        raise ValueError(f"Invalid file manager type: {type_}")
