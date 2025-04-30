"""Simple OTEL collector server that logs all incoming requests."""

import argparse
import json
from datetime import datetime
from typing import Any

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

app = FastAPI(title="OTEL Collector")
app.state.debug_mode = False


async def log_request(request: Request, body: Any) -> None:
    """Log the details of an incoming request."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    print(f"\n=== Received OTEL Request at {timestamp} ===")
    print(f"Method: {request.method}")
    print(f"Path: {request.url.path}")

    if request.app.state.debug_mode:
        print("\nHeaders:")
        for key, value in request.headers.items():
            print(f"  {key}: {value}")

    print("\nBody:")
    print(json.dumps(body, indent=2))
    print("=" * 50)
    print()  # Add a blank line for readability


@app.post("/v1/traces", status_code=status.HTTP_200_OK)
async def collect_traces(request: Request) -> JSONResponse:
    """Collect and log trace data."""
    body = await request.json()
    await log_request(request, body)
    return JSONResponse({"status": "success"})


@app.post("/v1/metrics", status_code=status.HTTP_200_OK)
async def collect_metrics(request: Request) -> JSONResponse:
    """Collect and log metrics data."""
    body = await request.json()
    await log_request(request, body)
    return JSONResponse({"status": "success"})


@app.post("/v1/logs", status_code=status.HTTP_200_OK)
async def collect_logs(request: Request) -> JSONResponse:
    """Collect and log log data."""
    body = await request.json()
    await log_request(request, body)
    return JSONResponse({"status": "success"})


def parse_args() -> tuple[str, int, bool]:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run a simple OTEL collector server that logs all requests.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind the server to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=4318,
        help="Port to run the server on (default: 4318)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show additional debug information like headers",
    )
    args = parser.parse_args()
    return args.host, args.port, args.debug


def main() -> None:
    """Run the OTEL collector server."""
    host, port, debug = parse_args()
    app.state.debug_mode = debug

    print("\nStarting OTEL collector")
    print(f"Server: {host}:{port}")
    print(f"Debug mode: {'enabled' if debug else 'disabled'}")
    print("Press Ctrl+C to stop\n")

    uvicorn.run(
        app,
        host=host,
        port=port,
    )


if __name__ == "__main__":
    main()
