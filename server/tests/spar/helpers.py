from dataclasses import dataclass
from pathlib import Path

from agent_platform.orchestrator.agent_server_client import AgentServerClient


@dataclass
class FileUploadResult:
    file_id: str
    file_ref: str


def upload_file_to_thread(
    agent_server_client: AgentServerClient, thread_id: str, file_path: str | Path
) -> FileUploadResult:
    file_response = agent_server_client.upload_file_to_thread(thread_id, str(file_path))
    file_upload_result = file_response.json()
    file_id = file_upload_result[0]["file_id"]
    file_ref = file_upload_result[0]["file_ref"]
    assert isinstance(file_id, str)
    assert isinstance(file_ref, str)
    return FileUploadResult(file_id, file_ref)
