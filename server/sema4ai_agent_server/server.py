import argparse
import hashlib
import os
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, urlunparse

import orjson
import structlog
from fastapi import FastAPI, Form, UploadFile
from fastapi.exceptions import HTTPException

from sema4ai_agent_server.api import router as api_router
from sema4ai_agent_server.api.files import _add_uploaded_messages, _store_files
from sema4ai_agent_server.auth.handlers import AuthedUser
from sema4ai_agent_server.constants import UPLOAD_DIR
from sema4ai_agent_server.lifespan import lifespan
from sema4ai_agent_server.log_config import setup_logging
from sema4ai_agent_server.schema import Agent, Thread, UploadedFile
from sema4ai_agent_server.storage.option import get_storage
from sema4ai_agent_server.tools import AvailableTools

setup_logging()
logger = structlog.get_logger(__name__)

# Ensure UPLOAD_DIR exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Determine the database type
DB_TYPE = os.environ.get("S4_AGENT_SERVER_DB_TYPE", "sqlite").lower()
# Get root of app, used to point to directory containing static files
ROOT = Path(__file__).parent.parent

app = FastAPI(title="OpenGPTs API", lifespan=lifespan)
app.include_router(api_router)


def _get_hash(file_content: bytes) -> str:
    hash = hashlib.sha256()
    hash.update(file_content)
    return hash.hexdigest()


@app.post("/ingest", description="Upload files to the given agent or thread.")
async def ingest_files(
    files: list[UploadFile],
    user: AuthedUser,
    config: str = Form(...),
) -> list[UploadedFile]:
    """Ingest a list of files."""
    config = orjson.loads(config)

    agent_id = config["configurable"].get("agent_id")
    thread_id = config["configurable"].get("thread_id")

    if agent_id is not None and thread_id is not None:
        raise HTTPException(
            status_code=400, detail="Indicate either agent_id or thread_id."
        )

    agent: Optional[Agent] = None
    if agent_id is not None:
        agent = await get_storage().get_agent(user.user_id, agent_id)
        if agent is None:
            raise HTTPException(status_code=404, detail="Agent not found.")

    thread: Optional[Thread] = None
    if thread_id is not None:
        thread = await get_storage().get_thread(user.user_id, thread_id)
        if thread is None:
            raise HTTPException(status_code=404, detail="Thread not found.")

    try:
        stored_files = await _store_files(thread or agent, files)
    except Exception as e:
        logger.exception("Failed to store a file", exception=e)
        raise HTTPException(status_code=500, detail=f"Failed to store a file: {str(e)}")

    if thread_id:
        await _add_uploaded_messages(stored_files, thread_id, user)

    return stored_files


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/metrics")
async def metrics() -> dict:
    return {
        "agentCount": await get_storage().agent_count(),
        "threadCount": await get_storage().thread_count(),
    }


@app.post("/update-action-server-ports")
async def update_action_server_ports(port_map: dict[str, str]) -> dict:
    logger.info(f"Updating action server ports: {port_map}")
    if not port_map:
        logger.error("Port map not provided.")
        raise HTTPException(status_code=400, detail="Port map not provided.")

    agents = await get_storage().list_all_agents()
    updated_agents = []

    for agent in agents:
        updated = False
        for tool in agent.config.get("configurable", {}).get("tools", []):
            if tool["type"] != AvailableTools.ACTION_SERVER:
                continue

            url = tool["config"]["url"]
            parts = urlparse(url)

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
            tool["config"]["url"] = new_url
            updated = True
            logger.info(f"Updated tool URL from {url} to {new_url} for {agent.name}.")

        if updated:
            updated_agents.append(agent)

    for agent in updated_agents:
        await get_storage().put_agent(
            user_id=agent.user_id,
            agent_id=agent.id,
            name=agent.name,
            config=agent.config,
            public=agent.public,
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
