from pathlib import Path

from sema4ai.common.locations import get_default_executable_path
from sema4ai.common.locations import (
    get_default_sema4ai_home_dir as common_get_default_sema4ai_home_dir,
)
from sema4ai.common.tools import BaseTool

# APIs below kept for backward compatibility
get_default_sema4ai_home_dir = common_get_default_sema4ai_home_dir
get_executable_path = get_default_executable_path

DEFAULT_ACTION_SERVER_VERSION = "2.17.0"


def get_action_server_executable_path(version: str = DEFAULT_ACTION_SERVER_VERSION, download: bool = True) -> Path:
    from sema4ai.common import tools

    target_location = tools.ActionServerTool.get_default_executable(version=version, download=download)
    return target_location


class AgentServerTool(BaseTool):
    mutex_name = "sema4ai-get-agent-server"
    base_url = "https://cdn.sema4.ai/agent-server"
    executable_name = "agent-server"
    macos_arm_64_download_path: str = "macos_arm64"
    linux64_download_path: str = "linux_x64"

    make_run_check = False

    def __init__(self, target_location: str, tool_version: str):
        super().__init__(target_location, tool_version)


def get_agent_server_executable_path(version: str, download: bool = False) -> Path:
    target_location = AgentServerTool.get_default_executable(version=version, download=download)
    return target_location
