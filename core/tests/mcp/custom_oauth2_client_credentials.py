"""
FastAPI OAuth2 test server for client credentials authentication.

This server implements the OAuth2 client_credentials grant type for testing purposes.
It uses simple static credentials:
- client_id: dummy_client_id
- client_secret: dummy_client_secret
- access_token: dummy_token
"""

from fastapi import FastAPI, Form, HTTPException, status
from pydantic import BaseModel

# Static credentials for testing
DUMMY_CLIENT_ID = "dummy-client-id"
DUMMY_CLIENT_SECRET = "dummy-client-secret"
DUMMY_ACCESS_TOKEN = "dummy-token"


class TokenResponse(BaseModel):
    """OAuth2 token response model."""

    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 3600  # 1 hour in seconds


app = FastAPI(title="OAuth2 Client Credentials Test Server")


@app.post("/token", response_model=TokenResponse)
async def token_endpoint(
    grant_type: str = Form(...),
    client_id: str = Form(...),
    client_secret: str = Form(...),
    scope: str | None = Form(None),
) -> TokenResponse:
    """
    OAuth2 token endpoint for client_credentials grant type.

    Validates client credentials and returns an access token.
    """
    # Validate grant_type
    if grant_type != "client_credentials":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported grant_type. Only 'client_credentials' is supported.",
        )

    # Validate client credentials
    if client_id != DUMMY_CLIENT_ID or client_secret != DUMMY_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid client credentials",
        )

    # Return access token
    return TokenResponse(
        access_token=DUMMY_ACCESS_TOKEN,
        token_type="Bearer",
        expires_in=3600,
    )


@app.get("/")
async def root():
    """Root endpoint for health checks."""
    return {"message": "OAuth2 Client Credentials Test Server", "status": "running"}


if __name__ == "__main__":
    import sys

    import uvicorn

    if len(sys.argv) < 2:
        print("Usage: python custom_oauth2_client_credentials.py <port>")
        sys.exit(1)

    port = int(sys.argv[1])

    uvicorn.run(app, host="127.0.0.1", port=port)
