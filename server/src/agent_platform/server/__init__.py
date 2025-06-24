from importlib.metadata import version

from agent_platform.server.main import main

# Load version from metadata
__version__ = version("agent_platform_server")

__all__ = ["main"]
