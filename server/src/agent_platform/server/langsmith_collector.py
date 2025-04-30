"""Simple LangSmith collector server that logs all incoming traces."""

import argparse
import json
from datetime import datetime
from typing import Any

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

app = FastAPI(title="LangSmith Collector")
app.state.debug_mode = False


def format_messages(messages: list[dict[str, Any]]) -> str:
    """Format chat messages for readable display."""
    formatted = []
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        formatted.append(f"\n  {role}: {content}")
    return "".join(formatted)


async def log_run(request: Request, body: dict[str, Any]) -> None:
    """Log the details of a run in a readable format."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    print(f"\n=== Received LangSmith Run at {timestamp} ===")

    # Basic run info
    run_id = body.get("id", "unknown")
    name = body.get("name", "unknown")
    run_type = body.get("run_type", "unknown")
    start_time = body.get("start_time", "unknown")
    end_time = body.get("end_time", "unknown")
    error = body.get("error")

    print(f"Run ID: {run_id}")
    print(f"Name: {name}")
    print(f"Type: {run_type}")
    print(f"Start: {start_time}")
    print(f"End: {end_time}")

    # Inputs
    inputs = body.get("inputs", {})
    print("\nInputs:")
    if isinstance(inputs, dict):
        if "messages" in inputs:
            print("Chat Messages:", format_messages(inputs["messages"]))
        else:
            for k, v in inputs.items():
                print(f"  {k}: {v}")
    else:
        print(f"  {inputs}")

    # Outputs
    outputs = body.get("outputs", {})
    print("\nOutputs:")
    if isinstance(outputs, dict):
        if "messages" in outputs:
            print("Chat Messages:", format_messages(outputs["messages"]))
        else:
            for k, v in outputs.items():
                print(f"  {k}: {v}")
    else:
        print(f"  {outputs}")

    # Error if present
    if error:
        print("\nError:")
        print(f"  {error}")

    if request.app.state.debug_mode:
        print("\nFull Run Data:")
        print(json.dumps(body, indent=2))

    print("=" * 50)
    print()


@app.post("/runs", status_code=status.HTTP_200_OK)
async def collect_run(request: Request) -> JSONResponse:
    """Collect and log run data."""
    body = await request.json()
    await log_run(request, body)
    return JSONResponse({"status": "success"})


@app.post("/datasets", status_code=status.HTTP_200_OK)
async def collect_dataset(request: Request) -> JSONResponse:
    """Collect and log dataset operations."""
    body = await request.json()
    if request.app.state.debug_mode:
        print("\n=== Received Dataset Operation ===")
        print(json.dumps(body, indent=2))
        print("=" * 50)
        print()
    return JSONResponse({"status": "success"})


def parse_args() -> tuple[str, int, bool]:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run a simple LangSmith collector server that logs all requests.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind the server to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=1984,  # Default LangSmith port
        help="Port to run the server on (default: 1984)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show additional debug information including raw JSON",
    )
    args = parser.parse_args()
    return args.host, args.port, args.debug


def main() -> None:
    """Run the LangSmith collector server."""
    host, port, debug = parse_args()
    app.state.debug_mode = debug

    print("\nStarting LangSmith collector")
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
