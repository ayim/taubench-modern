import argparse
import hashlib
import os
from pathlib import Path
from urllib.parse import urlparse, urlunparse
from uuid import uuid4

import orjson
import structlog
from fastapi import FastAPI, Form, UploadFile
from fastapi.exceptions import HTTPException
from starlette.background import BackgroundTasks

from app.api import router as api_router
from app.auth.handlers import AuthedUser
from app.lifespan import lifespan
from app.log_config import setup_logging
from app.schema import UploadedFile
from app.storage.option import get_storage
from app.tools import AvailableTools
from app.upload import convert_ingestion_input_to_blob, ingest_runnable

setup_logging()
logger = structlog.get_logger(__name__)

SEMA4AIDESKTOP_HOME = os.getenv("S4_AGENT_SERVER_HOME", ".")
UPLOAD_DIR = os.path.join(SEMA4AIDESKTOP_HOME, "uploads")
# Ensure UPLOAD_DIR exists
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="OpenGPTs API", lifespan=lifespan)


# Get root of app, used to point to directory containing static files
ROOT = Path(__file__).parent.parent


app.include_router(api_router)


def _get_hash(file_content: bytes) -> str:
    hash = hashlib.sha256()
    hash.update(file_content)
    return hash.hexdigest()


@app.post("/ingest", description="Upload files to the given assistant or thread.")
async def ingest_files(
    files: list[UploadFile],
    user: AuthedUser,
    background_tasks: BackgroundTasks,
    config: str = Form(...),
) -> list[UploadedFile]:
    """Ingest a list of files."""
    config = orjson.loads(config)

    assistant_id = config["configurable"].get("assistant_id")
    thread_id = config["configurable"].get("thread_id")

    if assistant_id is not None and thread_id is not None:
        raise HTTPException(
            status_code=400, detail="Indicate either assistant_id or thread_id."
        )

    if assistant_id is not None:
        assistant = await get_storage().get_assistant(user["user_id"], assistant_id)
        if assistant is None:
            raise HTTPException(status_code=404, detail="Assistant not found.")

    if thread_id is not None:
        thread = await get_storage().get_thread(user["user_id"], thread_id)
        if thread is None:
            raise HTTPException(status_code=404, detail="Thread not found.")

    file_blobs = [convert_ingestion_input_to_blob(file) for file in files]

    # Store files

    non_ingestable_extensions = {".csv", ".xls", ".xlsx", ".json", ".xml"}
    ingestable_file_blobs = []
    stored_files = []
    for file_blob in file_blobs:
        filename = file_blob.path
        file_path = os.path.join(UPLOAD_DIR, assistant_id or thread_id, filename)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        file_hash = _get_hash(file_blob.data)
        existing_file = await get_storage().get_file(file_path)
        file_already_exists = existing_file and existing_file["file_hash"] == file_hash
        if file_already_exists:
            stored_files.append(existing_file)
            continue

        try:
            with open(file_path, "wb") as out_file:
                out_file.write(file_blob.data)
            # Check the file extension
            file_extension = os.path.splitext(filename)[1].lower()
            ingestable = file_extension not in non_ingestable_extensions
            if ingestable:
                ingestable_file_blobs.append(file_blob)
            stored_file = await get_storage().put_file_owner(
                str(uuid4()), file_path, file_hash, ingestable, assistant_id, thread_id
            )
            stored_files.append(stored_file)
        except Exception as e:
            logger.exception(f"Failed to store file {filename}")
            raise HTTPException(
                status_code=500, detail=f"Failed to store file {filename}: {str(e)}"
            )

    ingest_runnable.batch(ingestable_file_blobs, config)
    return stored_files


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/metrics")
async def metrics() -> dict:
    return {
        "agentCount": await get_storage().assistant_count(),
        "threadCount": await get_storage().thread_count(),
    }


@app.post("/update-action-server-ports")
async def update_action_server_ports(port_map: dict[str, str]) -> dict:
    logger.info(f"Updating action server ports: {port_map}")
    if not port_map:
        logger.error("Port map not provided.")
        raise HTTPException(status_code=400, detail="Port map not provided.")

    assistants = await get_storage().list_all_assistants()
    updated_assistants = []

    for assistant in assistants:
        updated = False
        for tool in (
            assistant["config"].get("configurable", {}).get("type==agent/tools", [])
        ):
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
            logger.info(
                f"Updated tool URL from {url} to {new_url} for {assistant['name']}."
            )

        if updated:
            updated_assistants.append(assistant)

    for assistant in updated_assistants:
        await get_storage().put_assistant(
            user_id=assistant["user_id"],
            assistant_id=assistant["assistant_id"],
            name=assistant["name"],
            config=assistant["config"],
            public=assistant["public"],
            metadata=assistant["metadata"],
        )

    logger.info(f"Ports updated for {len(updated_assistants)} assistants.")
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
    uvicorn.run("app.server:app", host="0.0.0.0", port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
