import logging
import os

"""
Logging configuration for doc-extraction.
"""

logger: logging.Logger = logging.getLogger("sema4ai_docint")
# copy reducto's packages for logging
reducto_logger: logging.Logger = logging.getLogger("reducto")
httpx_logger: logging.Logger = logging.getLogger("httpx")


def _basic_config() -> None:
    logging.basicConfig(
        format="%(asctime)s - %(name)s - %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _setup_logging() -> None:
    # Pull a log level from envvar, map it to a logging.Level
    env = os.environ.get("SEMA4AI_LOG_LEVEL", "INFO").upper()
    level = logging.getLevelNamesMapping().get(env, logging.INFO)

    # Set up all loggers at the same level
    _basic_config()
    for logger_instance in (logger, reducto_logger, httpx_logger):
        logger_instance.setLevel(level)
