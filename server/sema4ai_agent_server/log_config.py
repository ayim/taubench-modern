import logging
import sys
from logging.handlers import RotatingFileHandler

import structlog
from pythonjsonlogger import jsonlogger
from uvicorn.logging import AccessFormatter, DefaultFormatter

from sema4ai_agent_server.constants import SystemConfig, SystemPaths


def setup_logging():
    level = getattr(logging, SystemConfig.log_level, None)
    if not isinstance(level, int):
        raise ValueError(f"Invalid log level: {SystemConfig.log_level}")

    default_formatter = DefaultFormatter(
        "%(asctime)s - %(name)s - %(levelprefix)s %(message)s"
    )
    access_formatter = AccessFormatter(
        '%(asctime)s - %(name)s - %(levelprefix)s  %(client_addr)s - "%(request_line)s" %(status_code)s'
    )
    json_formatter = jsonlogger.JsonFormatter(
        "%(asctime)s - %(name)s - %(levelname)s %(message)s"
    )

    default_handler = logging.StreamHandler(sys.stderr)
    default_handler.setFormatter(default_formatter)
    access_handler = logging.StreamHandler(sys.stdout)
    access_handler.setFormatter(access_formatter)
    file_handler = RotatingFileHandler(
        SystemPaths.log_file_path,
        maxBytes=SystemConfig.log_file_size,
        backupCount=SystemConfig.log_max_backup_files,
    )
    file_handler.setFormatter(json_formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(default_handler)
    root_logger.addHandler(file_handler)

    app_logger = logging.getLogger("app")
    app_logger.setLevel(level)
    app_logger.addHandler(default_handler)
    app_logger.addHandler(file_handler)
    app_logger.propagate = False

    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.setLevel(level)
    uvicorn_logger.handlers.clear()
    uvicorn_logger.addHandler(default_handler)
    uvicorn_logger.addHandler(file_handler)
    uvicorn_logger.propagate = False

    sseclient_logger = logging.getLogger("sseclient")
    sseclient_logger.setLevel(level)
    sseclient_logger.handlers.clear()
    sseclient_logger.addHandler(default_handler)
    sseclient_logger.addHandler(file_handler)
    sseclient_logger.propagate = False

    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_access_logger.setLevel(level)
    uvicorn_access_logger.handlers.clear()
    uvicorn_access_logger.addHandler(access_handler)
    uvicorn_access_logger.addHandler(file_handler)
    uvicorn_access_logger.propagate = False

    # Prevents getting spammed with watchfiles logs when --reload is used in development
    watchfiles_logger = logging.getLogger("watchfiles.main")
    watchfiles_logger.setLevel(logging.WARNING)
    watchfiles_logger.propagate = False

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.UnicodeDecoder(),
            structlog.stdlib.render_to_log_kwargs,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
