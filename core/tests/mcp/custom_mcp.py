from fastapi import Request
from mcp.server.fastmcp import FastMCP
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp

# Create the FastMCP server instance
mcp = FastMCP("Custom MCP Server")


class TokenVerificationMiddleware(BaseHTTPMiddleware):
    """Middleware that verifies the Authorization Bearer token in requests."""

    def __init__(self, app: ASGIApp, expected_token: str = "dummy-token"):
        super().__init__(app)
        self.expected_token = expected_token

    async def dispatch(self, request: Request, call_next):
        # Extract Authorization header
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return Response(
                status_code=401,
                content="Missing Authorization header",
            )

        # Check if it's a Bearer token
        if not auth_header.startswith("Bearer "):
            return Response(
                status_code=401,
                content="Invalid Authorization header format. Expected 'Bearer <token>'",
            )

        # Extract the token
        token = auth_header[7:].strip()  # Remove "Bearer " prefix

        # Verify the token
        if token != self.expected_token:
            return Response(
                status_code=403,
                content="Invalid token",
            )

        # Token is valid, proceed with the request
        return await call_next(request)


@mcp.tool(
    "dummy_tool",
    description="A dummy tool that returns a simple message",
)
async def dummy_tool(message: str = "Hello from dummy tool") -> str:
    """A dummy tool that echoes back a message."""
    return f"Dummy tool response: {message}"


# Create the HTTP app with token verification middleware
if __name__ == "__main__":
    import sys

    import uvicorn

    if len(sys.argv) < 3:
        print("Usage: python custom_mcp.py <port> <expected_token>")
        sys.exit(1)

    port = sys.argv[1]
    expected_token = sys.argv[2]

    app = mcp.streamable_http_app()
    app.add_middleware(TokenVerificationMiddleware, expected_token=expected_token)
    uvicorn.run(app, host="127.0.0.1", port=int(port))
