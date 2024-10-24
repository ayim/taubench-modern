import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("SEMA4AI_STUDIO_HOME", "."))
LOG_DIR = Path(os.environ.get("SEMA4AI_STUDIO_LOG", "."))
VECTOR_DATABASE_PATH = str(DATA_DIR / "chroma_db")
DOMAIN_DATABASE_PATH = str(DATA_DIR / "agentserver.db")
UPLOAD_DIR = str(DATA_DIR / "uploads")
LOG_FILE_PATH = str(LOG_DIR / "agent-server.log")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
DEBUG_MODE = LOG_LEVEL in ["DEBUG", "TRACE"]
