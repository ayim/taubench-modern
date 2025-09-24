"""Set of modules for parsing CLI arguments for the Agent Server."""

from agent_platform.server.cli.args import ServerArgs, parse_args, set_no_logging
from agent_platform.server.cli.configurations import (
    parse_config_path_args,
    print_config,
)
from agent_platform.server.cli.license import print_license
from agent_platform.server.cli.lifecycle import ServerLifecycleManager
from agent_platform.server.cli.openapi import print_openapi_spec

__all__ = [
    "ServerArgs",
    "ServerLifecycleManager",
    "parse_args",
    "parse_config_path_args",
    "print_config",
    "print_license",
    "print_openapi_spec",
    "set_no_logging",
]
