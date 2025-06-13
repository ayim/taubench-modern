import logging
import sys
from os import getenv

import uvicorn
from fastapi import FastAPI
from uvicorn.logging import DefaultFormatter

from .lifecycle import make_app


def _configure_logging() -> None:
    """
    Configure logging for the workitems service.
    """

    default_handler = logging.StreamHandler(sys.stderr)
    formatter = DefaultFormatter(
        "%(asctime)s - %(name)s - %(levelprefix)s %(message)s",
        use_colors=True,
    )
    default_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()
    root_logger.addHandler(default_handler)


def main() -> None:
    _configure_logging()

    app = FastAPI()
    app.mount("/api/work-items", make_app())
    uvicorn.run(app, host="0.0.0.0", port=int(getenv("PORT", "8000")))


if __name__ == "__main__":
    main()
