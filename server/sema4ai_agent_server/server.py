import argparse
import os
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import structlog
import tomllib
from fastapi import FastAPI
from fastapi.exceptions import HTTPException

from sema4ai_agent_server.api import router as api_router
from sema4ai_agent_server.constants import UPLOAD_DIR
from sema4ai_agent_server.lifespan import lifespan
from sema4ai_agent_server.log_config import setup_logging
from sema4ai_agent_server.storage.option import get_storage

setup_logging()
logger = structlog.get_logger(__name__)

# Ensure UPLOAD_DIR exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Determine the database type
DB_TYPE = os.environ.get("S4_AGENT_SERVER_DB_TYPE", "sqlite").lower()
# Get root of app, used to point to directory containing static files
ROOT = Path(__file__).parent.parent

# Read current Agent Server version
with open(ROOT / "pyproject.toml", "rb") as f:
    pyproject_data = tomllib.load(f)
version = pyproject_data["tool"]["poetry"]["version"]

app = FastAPI(title="Sema4.ai Agent Server API", lifespan=lifespan, version=version)
app.include_router(api_router)


@app.get("/api/v1/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/api/v1/metrics")
async def metrics() -> dict:
    return {
        "agentCount": await get_storage().agent_count(),
        "threadCount": await get_storage().thread_count(),
    }


@app.post("/api/v1/update-action-server-ports")
async def update_action_server_ports(port_map: dict[str, str]) -> dict:
    logger.info(f"Updating action server ports: {port_map}")
    if not port_map:
        logger.error("Port map not provided.")
        raise HTTPException(status_code=400, detail="Port map not provided.")

    agents = await get_storage().list_all_agents()
    updated_agents = []

    for agent in agents:
        updated = False
        for action_package in agent.action_packages:
            parts = urlparse(action_package.url)

            if parts.port is None or str(parts.port) not in port_map:
                continue

            new_url = urlunparse(
                (
                    parts.scheme,
                    f"{parts.hostname}:{port_map[str(parts.port)]}",
                    parts.path,
                    parts.params,
                    parts.query,
                    parts.fragment,
                )
            )
            action_package.url = new_url
            updated = True
            logger.info(
                f"Updated tool URL from {action_package.url} to {new_url} for {agent.name}."
            )

        if updated:
            updated_agents.append(agent)

    for agent in updated_agents:
        await get_storage().put_agent(
            user_id=agent.user_id,
            agent_id=agent.id,
            public=agent.public,
            status=agent.status,
            name=agent.name,
            description=agent.description,
            runbook=agent.runbook,
            version=agent.version,
            model=agent.model,
            architecture=agent.architecture,
            reasoning=agent.reasoning,
            action_packages=agent.action_packages,
            metadata=agent.metadata,
        )

    logger.info(f"Ports updated for {len(updated_agents)} agents.")
    return {"status": "ok"}


def main():
    import uvicorn

    parser = argparse.ArgumentParser(description="Run the Sema4.ai Agent Server.")
    parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=8100,
        help="Port to run the HTTP server on. Default is 8100.",
    )
    parser.add_argument(
        "-r",
        "--reload",
        action="store_true",
        help="Enable auto-reload of the server on code changes.",
    )

    args = parser.parse_args()
    uvicorn.run("server:app", host="0.0.0.0", port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
