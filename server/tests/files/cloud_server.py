import os
import shutil
import time
from dataclasses import dataclass
from datetime import UTC, datetime

import jwt
import uvicorn
from fastapi import FastAPI, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse


def log(message: str) -> None:
    """Add timestamp to log messages"""
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {message}")


app = FastAPI()

# Configuration
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "temp_uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
SECRET_KEY = "your-secret-key-here"

# Store file metadata
files_metadata: dict[str, dict] = {}


@dataclass
class PresignedPostRequest:
    file_id: str
    expires_in: int


@app.post("/")
async def handle_presigned_post(request: PresignedPostRequest):
    """
    Endpoint for getting presigned POST URL
    Called by CFM's _get_presigned_post method
    """
    log(f"Generating presigned POST URL for file ID: {request.file_id}")
    token = jwt.encode(
        {"file_id": request.file_id, "exp": int(time.time()) + request.expires_in},
        SECRET_KEY,
        algorithm="HS256",
    )

    return {
        "url": "http://localhost:8001/upload",
        "form_data": {"token": token, "file_id": request.file_id},
    }


@app.get("/")
async def handle_presigned_url(file_id: str, file_name: str, expires_in: int):
    """
    Endpoint for getting presigned download URL
    Called by CFM's _get_presigned_url method
    """
    log(f"Generating presigned URL for file: {file_name} (ID: {file_id})")
    if not os.path.exists(os.path.join(UPLOAD_DIR, file_id)):
        raise HTTPException(status_code=404, detail="File not found")

    token = jwt.encode(
        {
            "file_id": file_id,
            "file_name": file_name,
            "exp": int(time.time()) + expires_in,
        },
        SECRET_KEY,
        algorithm="HS256",
    )

    return {"url": f"http://localhost:8001/download/{file_id}?token={token}"}


@app.delete("/")
async def handle_delete(request: Request):
    """
    Endpoint for file deletion
    Called by CFM's _delete_stored_file method
    """
    data = await request.json()
    file_id = data.get("fileId")
    log(f"Deleting file: {file_id}")

    file_path = os.path.join(UPLOAD_DIR, file_id)
    if not os.path.exists(file_path):
        return {"deleted": False}

    try:
        os.remove(file_path)
        files_metadata.pop(file_id, None)
        return {"deleted": True}
    except Exception:
        return {"deleted": False}


@app.post("/upload")
async def handle_upload(
    file: UploadFile,
    token: str = Form(...),
    file_id: str = Form(...),
):
    """
    Endpoint for actual file upload
    Called after getting presigned POST URL
    """
    try:
        # Verify token
        jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        log(f"Handling file upload for ID: {file_id}")

        file_path = os.path.join(UPLOAD_DIR, file_id)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        files_metadata[file_id] = {
            "original_name": file.filename,
            "content_type": file.content_type,
            "upload_time": datetime.now(UTC).isoformat(),
        }

        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/download/{file_id}")
async def handle_download(file_id: str, token: str):
    """
    Endpoint for file download
    Called using presigned URL
    """
    try:
        # Verify token
        jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        log(f"Handling file download for ID: {file_id}")

        file_path = os.path.join(UPLOAD_DIR, file_id)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="File not found")

        return FileResponse(
            file_path,
            media_type=files_metadata.get(file_id, {}).get(
                "content_type",
                "application/octet-stream",
            ),
        )
    except jwt.ExpiredSignatureError as e:
        raise HTTPException(status_code=401, detail="Token expired") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


if __name__ == "__main__":
    log("Starting File Management Server on http://localhost:8001")
    log(f"Files will be stored in: {os.path.abspath(UPLOAD_DIR)}")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_config={
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "()": "uvicorn.logging.DefaultFormatter",
                    "fmt": "[%(asctime)s.%(msecs)03d] %(levelprefix)s %(message)s",
                    "datefmt": "%Y-%m-%d %H:%M:%S",
                },
            },
            "handlers": {
                "default": {
                    "formatter": "default",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stderr",
                },
            },
            "loggers": {
                "uvicorn": {"handlers": ["default"], "level": "INFO"},
            },
        },
    )
