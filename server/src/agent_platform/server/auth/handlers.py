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

from agent_platform.core.user import User
from agent_platform.server.api import StorageDependency
from agent_platform.server.auth.settings import (
    AuthConfig,
    AuthType,
    JWTSettingsLocal,
    JWTSettingsOIDC,
)
from agent_platform.server.storage import BaseStorage


class AuthHandler(ABC):
    def __init__(self, storage: StorageDependency):
        self._storage = storage

    @property
    def storage(self) -> BaseStorage:
        return self._storage

    @abstractmethod
    async def handle(self, request: Request) -> User:
        """Auth handler that returns a user object or raises an HTTPException."""


class NOOPAuth(AuthHandler):
    _default_sub = "static-default-user-id"

    async def handle(self, request: Request) -> User:
        sub = request.cookies.get("agent_server_user_id") or self._default_sub
        user, _ = await self.storage.get_or_create_user(sub)
        return user


class JWTAuthBase(AuthHandler):
    async def handle(self, request: Request) -> User:
        http_bearer = await HTTPBearer()(request)
        if not http_bearer:
            raise HTTPException(status_code=401, detail="No token provided")
        token = http_bearer.credentials

        try:
            payload = self.decode_token(token, self.get_decode_key(token))
        except jwt.PyJWTError as e:
            raise HTTPException(status_code=401, detail=str(e)) from e

        user, _ = await self.storage.get_or_create_user(payload["sub"])
        return user

    @abstractmethod
    def decode_token(self, token: str, decode_key: str) -> dict: ...

    @abstractmethod
    def get_decode_key(self, token: str) -> str: ...


class JWTAuthLocal(JWTAuthBase):
    """Auth handler that uses a hardcoded decode key from env."""

    def decode_token(self, token: str, decode_key: str) -> dict:
        if (
            not isinstance(AuthConfig.jwt_settings, JWTSettingsLocal)
            or not AuthConfig.jwt_settings
        ):
            raise HTTPException(status_code=401, detail="No local JWT settings")
        return jwt.decode(
            token,
            decode_key,
            issuer=AuthConfig.jwt_settings.iss,
            audience=AuthConfig.jwt_settings.aud,
            algorithms=[AuthConfig.jwt_settings.alg.upper()],
            options={"require": ["exp", "iss", "aud", "sub"]},
        )

    def get_decode_key(self, token: str) -> str:
        if (
            not isinstance(AuthConfig.jwt_settings, JWTSettingsLocal)
            or not AuthConfig.jwt_settings
        ):
            raise HTTPException(status_code=401, detail="No local JWT settings")
        if not AuthConfig.jwt_settings.decode_key:
            raise HTTPException(status_code=401, detail="No local JWT decode key")
        return AuthConfig.jwt_settings.decode_key


class JWTAuthOIDC(JWTAuthBase):
    """Auth handler that uses OIDC discovery to get the decode key."""

    _jwk_client_cache: ClassVar[dict[str, jwt.PyJWKClient]] = {}
    _decode_key_cache: ClassVar[dict[str, dict]] = {}

    def decode_token(self, token: str, decode_key: str) -> dict:
        alg = self._decode_complete_unverified(token)["header"]["alg"]
        if (
            not isinstance(AuthConfig.jwt_settings, JWTSettingsOIDC)
            or not AuthConfig.jwt_settings
        ):
            raise HTTPException(status_code=401, detail="No OIDC settings")
        return jwt.decode(
            token,
            decode_key,
            issuer=AuthConfig.jwt_settings.iss,
            audience=AuthConfig.jwt_settings.aud,
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


# TODO: @kylie-bee: I don't think we need to cache as FastAPI likely does caching.
@lru_cache(maxsize=1)
def get_auth_handler(storage: StorageDependency) -> AuthHandler:
    if AuthConfig.auth_type == AuthType.JWT_LOCAL:
        return JWTAuthLocal(storage)
    elif AuthConfig.auth_type == AuthType.JWT_OIDC:
        return JWTAuthOIDC(storage)
    return NOOPAuth(storage)


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
        "headers": [
            (k.lower().encode(), v.encode()) for k, v in websocket.headers.items()
        ],
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
