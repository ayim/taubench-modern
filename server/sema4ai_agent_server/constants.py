import os
from pathlib import Path


def _normalized_path(path: str) -> Path:
    return Path(os.path.normpath(os.path.abspath(path)))


# It's a bit strange that the agent server references SEMA4AI_STUDIO_XXX constants...
# Still, keeping it for now to avoid breaking changes.

if os.getenv("S4_AGENT_SERVER_HOME"):
    DATA_DIR = _normalized_path(os.environ["S4_AGENT_SERVER_HOME"])
else:
    # No S4_AGENT_SERVER_HOME, use the SEMA4AI_STUDIO_XXX related constants
    # or fallback to the current directory.
    DATA_DIR = _normalized_path(os.environ.get("SEMA4AI_STUDIO_HOME", "."))

if os.environ.get("SEMA4AI_STUDIO_LOG"):
    LOG_DIR = _normalized_path(os.environ["SEMA4AI_STUDIO_LOG"])
else:
    LOG_DIR = DATA_DIR


VECTOR_DATABASE_PATH = str(DATA_DIR / "chroma_db")
DOMAIN_DATABASE_PATH = str(DATA_DIR / "agentserver.db")
LOG_FILE_PATH = str(LOG_DIR / "agent-server.log")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
S4_AGENT_SERVER_LOG_MAX_BACKUP_FILES = int(
    os.environ.get("S4_AGENT_SERVER_LOG_MAX_BACKUP_FILES", 5)
)
S4_AGENT_SERVER_LOG_FILE_SIZE = int(
    os.environ.get("S4_AGENT_SERVER_LOG_FILE_SIZE", 1_048_576 * 10)
)
DEBUG_MODE = LOG_LEVEL in ["DEBUG", "TRACE"]


class Constants:
    """
    Helper class to store constants (for now just the upload dir
    to avoid having to change all the code for the other constants).

    Constants are stored in this class and not at the module level so
    that they can be changed without worrying about imports that gather
    a reference to the constant explicitly (in which case, changing the
    related value in tests wouldn't change values for existing imports).
    """

    UPLOAD_DIR = str(DATA_DIR / "uploads")
