from abc import ABC, abstractmethod
from functools import lru_cache
from typing import Annotated, ClassVar

import jwt
import requests
from fastapi import (
    Depends,
    HTTPException,
    Request,
    WebSocket,
    WebSocketException,
    status,
)
from fastapi.security.http import HTTPBearer

from agent_server_types_v2.user import User
from sema4ai_agent_server.auth.settings import AuthType, settings
from sema4ai_agent_server.storage.v2.option_v2 import get_storage_v2


class AuthHandlerV2(ABC):
    @abstractmethod
    async def __call__(self, request: Request) -> User:
        """Auth handler that returns a user object or raises an HTTPException."""


class NOOPAuthV2(AuthHandlerV2):
    _default_sub = "static-default-user-id"

    async def __call__(self, request: Request) -> User:
        sub = request.cookies.get("agent_server_user_id") or self._default_sub
        user, _ = await get_storage_v2().get_or_create_user_v2(sub)
        return user


class JWTAuthBaseV2(AuthHandlerV2):
    async def __call__(self, request: Request) -> User:
        http_bearer = await HTTPBearer()(request)
        token = http_bearer.credentials

        try:
            payload = self.decode_token(token, self.get_decode_key(token))
        except jwt.PyJWTError as e:
            raise HTTPException(status_code=401, detail=str(e)) from e

        user, _ = await get_storage_v2().get_or_create_user_v2(payload["sub"])
        return user

    @abstractmethod
    def decode_token(self, token: str, decode_key: str) -> dict: ...

    @abstractmethod
    def get_decode_key(self, token: str) -> str: ...


class JWTAuthLocalV2(JWTAuthBaseV2):
    """Auth handler that uses a hardcoded decode key from env."""

    def decode_token(self, token: str, decode_key: str) -> dict:
        return jwt.decode(
            token,
            decode_key,
            issuer=settings.jwt_local.iss,
            audience=settings.jwt_local.aud,
            algorithms=[settings.jwt_local.alg.upper()],
            options={"require": ["exp", "iss", "aud", "sub"]},
        )

    def get_decode_key(self, token: str) -> str:
        return settings.jwt_local.decode_key


class JWTAuthOIDCV2(JWTAuthBaseV2):
    """Auth handler that uses OIDC discovery to get the decode key."""

    _jwk_client_cache: ClassVar[dict[str, jwt.PyJWKClient]] = {}
    _decode_key_cache: ClassVar[dict[str, dict]] = {}

    def decode_token(self, token: str, decode_key: str) -> dict:
        alg = self._decode_complete_unverified(token)["header"]["alg"]
        return jwt.decode(
            token,
            decode_key,
            issuer=settings.jwt_oidc.iss,
            audience=settings.jwt_oidc.aud,
            algorithms=[alg.upper()],
            options={"require": ["exp", "iss", "aud", "sub"]},
        )

    def get_decode_key(self, token: str) -> str:
        unverified = self._decode_complete_unverified(token)
        issuer = unverified["payload"].get("iss")
        kid = unverified["header"].get("kid")
        return self._get_jwk_client(issuer).get_signing_key(kid).key

    def _decode_complete_unverified(self, token: str) -> dict:
        if token not in self._decode_key_cache:
            self._decode_key_cache[token] = jwt.api_jwt.decode_complete(
                token,
                options={"verify_signature": False},
            )
        return self._decode_key_cache[token]

    def _get_jwk_client(self, issuer: str) -> jwt.PyJWKClient:
        """
        Cache jwk clients per issuer in a class-level dict instead of using lru_cache
        """
        if issuer not in self._jwk_client_cache:
            url = issuer.rstrip("/") + "/.well-known/openid-configuration"
            config = requests.get(url).json()
            self._jwk_client_cache[issuer] = jwt.PyJWKClient(
                config["jwks_uri"],
                cache_jwk_set=True,
            )
        return self._jwk_client_cache[issuer]

@lru_cache(maxsize=1)
def get_auth_handler_v2() -> AuthHandlerV2:
    if settings.auth_type == AuthType.JWT_LOCAL:
        return JWTAuthLocalV2()
    elif settings.auth_type == AuthType.JWT_OIDC:
        return JWTAuthOIDCV2()
    return NOOPAuthV2()


AuthHandlerDependency = Depends(get_auth_handler_v2)

async def auth_user_v2(
    request: Request, auth_handler: AuthHandlerV2 = AuthHandlerDependency,
):
    return await auth_handler(request)


async def auth_user_websocket_v2(
    websocket: WebSocket,
    auth_handler: AuthHandlerV2 = AuthHandlerDependency,
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
        "headers": [
            (k.lower().encode(), v.encode())
            for k, v in websocket.headers.items()
        ],
    }

    # Make a "fake" request object so we can re-use the auth handler
    fake_request = Request(http_scope)
    try:
        # Call the auth handler with the fake request
        return await auth_handler(fake_request)
    except HTTPException as exc:
        # If the auth handler raises an HTTPException, raise a WebSocketException
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason=str(exc.detail),
        ) from exc


def get_authed_user_v2():
    return Depends(auth_user_v2)


def get_authed_user_websocket_v2():
    return Depends(auth_user_websocket_v2)


AuthedUserV2 = Annotated[User, get_authed_user_v2()]
AuthedUserWebsocketV2 = Annotated[User, get_authed_user_websocket_v2()]
