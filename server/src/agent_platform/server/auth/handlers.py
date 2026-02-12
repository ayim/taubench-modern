import logging
from typing import Annotated

import jwt
from fastapi import (
    Depends,
    HTTPException,
    Request,
    WebSocket,
    WebSocketException,
    status,
)
from fastapi.security.http import HTTPBearer

from agent_platform.core.user import User
from agent_platform.server.storage import BaseStorage, StorageService

logger = logging.getLogger(__name__)

_StorageDependency = Annotated[BaseStorage, Depends(StorageService.get_instance)]


class AuthHandler:
    def __init__(self, storage: _StorageDependency):
        self._storage = storage

    async def handle(self, request: Request) -> User:
        http_bearer = await HTTPBearer()(request)
        if not http_bearer:
            raise HTTPException(status_code=401, detail="No token provided")
        token = http_bearer.credentials

        try:
            # The workroom backend produces unsigned JWTs (alg: "none") containing
            # only the `sub` claim as an identity transport mechanism.
            # See: workroom/backend/src/utils/signing.ts
            payload = jwt.decode(
                token,
                algorithms=["none"],
                options={
                    "verify_signature": False,
                    "verify_exp": False,
                    "require": ["sub"],
                },
            )
        except jwt.PyJWTError as e:
            raise HTTPException(status_code=401, detail=str(e)) from e

        user, _ = await self._storage.get_or_create_user(payload["sub"])
        return user


def get_auth_handler(storage: _StorageDependency) -> AuthHandler:
    return AuthHandler(storage)


AuthHandlerDependency = Annotated[AuthHandler, Depends(get_auth_handler)]


async def auth_user(
    request: Request,
    auth_handler: AuthHandlerDependency,
):
    return await auth_handler.handle(request)


async def auth_user_websocket(
    websocket: WebSocket,
    auth_handler: AuthHandlerDependency,
) -> User:
    """
    WebSocket authentication that mirrors the behavior of HTTP endpoint auth.
    Expects a Bearer token in the Authorization header.
    """
    # Create a proper HTTP scope from the WebSocket scope
    http_scope = {
        "type": "http",
        "method": "GET",
        "scheme": websocket.url.scheme,
        "server": (str(websocket.url.hostname), websocket.url.port),
        "path": websocket.url.path,
        "query_string": websocket.url.query.encode(),
        "headers": [(k.lower().encode(), v.encode()) for k, v in websocket.headers.items()],
    }

    # Make a "fake" request object so we can re-use the auth handler
    fake_request = Request(http_scope)
    try:
        # Call the auth handler with the fake request
        return await auth_handler.handle(fake_request)
    except HTTPException as exc:
        # If the auth handler raises an HTTPException, raise a WebSocketException
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason=str(exc.detail),
        ) from exc


AuthedUser = Annotated[User, Depends(auth_user)]
AuthedUserWebsocket = Annotated[User, Depends(auth_user_websocket)]
