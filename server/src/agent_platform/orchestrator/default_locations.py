from pathlib import Path

from sema4ai.common.locations import get_default_executable_path
from sema4ai.common.locations import (
    get_default_sema4ai_home_dir as common_get_default_sema4ai_home_dir,
)

# APIs below kept for backward compatibility
get_default_sema4ai_home_dir = common_get_default_sema4ai_home_dir
get_executable_path = get_default_executable_path


def get_action_server_executable_path(version: str, download: bool = False) -> Path:
    from sema4ai.common import tools

    target_location = tools.ActionServerTool.get_default_executable(
        version=version, download=download
    )
    return target_location
