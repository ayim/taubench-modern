import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import structlog
from uvicorn.logging import AccessFormatter, DefaultFormatter

from agent_platform.core.errors.base import PlatformError
from agent_platform.server.constants import SystemConfig, SystemPaths
from agent_platform.server.env_vars import LOG_LEVEL


def _platform_error_processor(logger, method_name, event_dict):
    """Extract error_id from PlatformError exceptions and inject into log message."""
    # TODO: This is a hack to get error_id into the event message. Currently, the logging
    # system does not take advantage of structlog's features and is due for a rework. ~ @kylie-bee
    exc_info = event_dict.get("exc_info")
    platform_error = None

    if exc_info and isinstance(exc_info, BaseException) and isinstance(exc_info, PlatformError):
        platform_error = exc_info
    elif exc_info is True:
        # Handle exc_info=True case - need to inspect the current exception
        current_exception = sys.exc_info()[1]
        if current_exception and isinstance(current_exception, PlatformError):
            platform_error = current_exception

    if platform_error:
        # Inject error_id directly into the log message
        error_id = platform_error.response.error_id
        current_event = event_dict.get("event", "")
        if error_id and f"error_id={error_id}" not in current_event:
            event_dict["event"] = f"{current_event} (error_id={error_id})"

    return event_dict


def _get_default_formatter(use_color: bool = True) -> logging.Formatter:
    """Set up default formatter for logging."""
    return DefaultFormatter(
        "%(asctime)s - %(name)s - %(levelprefix)s %(message)s",
        use_colors=use_color,
    )


def _get_access_handler() -> logging.StreamHandler:
    """Set up access handler for Uvicorn."""
    access_formatter = AccessFormatter(
        "%(asctime)s - %(name)s - %(levelprefix)s  "
        '%(client_addr)s - "%(request_line)s" %(status_code)s',
    )
    access_handler = logging.StreamHandler(sys.stdout)
    access_handler.setFormatter(access_formatter)
    return access_handler


def _get_file_handler() -> RotatingFileHandler:
    """Set up file handler for logging."""
    # If LOG_FILE_PATH does not exist, create it (recursively)
    try:
        path = Path(SystemPaths.log_file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass

    file_handler = RotatingFileHandler(
        SystemPaths.log_file_path,
        maxBytes=SystemConfig.log_file_size,
        backupCount=SystemConfig.log_max_backup_files,
    )
    file_handler.setFormatter(_get_default_formatter(use_color=False))
    return file_handler


def _setup_additional_loggers(
    level: int,
    default_handler: logging.Handler,
    file_handler: logging.Handler,
):
    """Set up additional loggers."""
    app_logger = logging.getLogger("app")
    app_logger.setLevel(level)
    app_logger.handlers.clear()
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
    uvicorn_access_logger.addHandler(_get_access_handler())
    uvicorn_access_logger.addHandler(file_handler)
    uvicorn_access_logger.propagate = False

    aiosqlite_logger = logging.getLogger("aiosqlite")
    aiosqlite_logger.setLevel(logging.WARNING)
    aiosqlite_logger.handlers.clear()
    aiosqlite_logger.addHandler(default_handler)
    aiosqlite_logger.addHandler(file_handler)
    aiosqlite_logger.propagate = False

    mcp_client_sse_logger = logging.getLogger("mcp.client.sse")
    mcp_client_sse_logger.addFilter(
        lambda record: "Unknown SSE event: ping" not in record.getMessage()
    )
    mcp_client_sse_logger.setLevel(logging.WARNING)
    mcp_client_sse_logger.handlers.clear()
    mcp_client_sse_logger.addHandler(default_handler)
    mcp_client_sse_logger.addHandler(file_handler)

    mcp_client_http_logger = logging.getLogger("mcp.client.streamable_http")
    mcp_client_http_logger.addFilter(
        lambda record: "Unknown SSE event: ping" not in record.getMessage()
    )
    mcp_client_http_logger.setLevel(logging.WARNING)
    mcp_client_http_logger.handlers.clear()
    mcp_client_http_logger.addHandler(default_handler)
    mcp_client_http_logger.addHandler(file_handler)

    # # Prevents getting spammed with watchfiles logs when
    # # --reload is used in development
    # watchfiles_logger = logging.getLogger("watchfiles.main")
    # watchfiles_logger.setLevel(logging.WARNING)
    # watchfiles_logger.propagate = False


def disable_logging() -> None:
    """Disable logging below ERROR across the server."""
    logging.disable(logging.WARNING)


def setup_logging(default_mode: bool = False, log_level: str | None = None):
    """Set up logging configuration.

    Args:
        default_mode: If True, use environment variables for minimal setup.
                     If False, use full system configuration.
        log_level: The log level to use. If None, tries to use environment
                   variable SEMA4AI_AGENT_SERVER_LOG_LEVEL or defaults to
                   "INFO".
    """
    if log_level is None:
        log_level = LOG_LEVEL if isinstance(LOG_LEVEL, str) else "INFO"
    if default_mode:
        level = getattr(logging, log_level)
    else:
        level = getattr(logging, SystemConfig.log_level, None)
    if not isinstance(level, int):
        raise ValueError(f"Invalid log level: {level}")

    # Set up handlers
    default_handler = logging.StreamHandler(sys.stderr)
    default_handler.setFormatter(_get_default_formatter())

    root_handlers = [default_handler]

    # Only set up additional loggers in full configuration mode
    if not default_mode:
        file_handler = _get_file_handler()
        root_handlers.append(file_handler)
        _setup_additional_loggers(level, default_handler, file_handler)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers.clear()

    # Configure uvicorn error logger
    uvicorn_error_logger = logging.getLogger("uvicorn.error")
    uvicorn_error_logger.setLevel(level)
    uvicorn_error_logger.handlers.clear()

    for handler in root_handlers:
        root_logger.addHandler(handler)
        uvicorn_error_logger.addHandler(handler)

    uvicorn_error_logger.propagate = False

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.UnicodeDecoder(),
            _platform_error_processor,
            structlog.stdlib.render_to_log_kwargs,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
