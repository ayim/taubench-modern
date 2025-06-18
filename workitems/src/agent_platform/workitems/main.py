import logging
import sys
from os import getenv

import uvicorn
from fastapi import FastAPI
from uvicorn.logging import DefaultFormatter

from .lifecycle import make_workitems_app


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
    agent_server_url = getenv("AGENT_SERVER_URL")
    if not agent_server_url:
        raise ValueError("AGENT_SERVER_URL is not set")

    _configure_logging()

    app = FastAPI()
    # Make a fake FastApi to mock out the agent client
    workitems_app = make_workitems_app(agent_server_url=agent_server_url)
    app.mount("/api/work-items", workitems_app)
    uvicorn.run(app, host="0.0.0.0", port=int(getenv("PORT", "8000")))


if __name__ == "__main__":
    main()
