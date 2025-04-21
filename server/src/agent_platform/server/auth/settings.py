from base64 import b64decode
from dataclasses import dataclass, field
from enum import Enum

from agent_platform.core.configurations import (
    Configuration,
    FieldMetadata,
)


class AuthType(Enum):
    NOOP = "noop"
    JWT_LOCAL = "jwt_local"
    JWT_OIDC = "jwt_oidc"


@dataclass
class JWTSettingsBase:
    iss: str = field(
        metadata=FieldMetadata(
            description="The issuer of the JWT token.",
            env_vars=["JWT_ISS"],
        ),
    )
    aud: str | list[str] = field(
        metadata=FieldMetadata(
            description="The audience of the JWT token.",
            env_vars=["JWT_AUD"],
        ),
    )

    def __post_init__(self):
        # Handle comma-separated audience strings
        if isinstance(self.aud, str) and "," in self.aud:
            self.aud = self.aud.split(",")


@dataclass
class JWTSettingsLocal(JWTSettingsBase):
    decode_key_b64: str = field(
        metadata=FieldMetadata(
            description="The base64 encoded private key of the JWT token.",
            env_vars=["JWT_DECODE_KEY_B64"],
        ),
    )
    alg: str = field(
        metadata=FieldMetadata(
            description="The algorithm of the JWT token.",
            env_vars=["JWT_ALG"],
        ),
    )
    decode_key: str | None = field(
        default=None,
        metadata=FieldMetadata(
            description="The private key of the JWT token.",
            env_vars=["JWT_DECODE_KEY"],
        ),
    )

    def __post_init__(self):
        super().__post_init__()
        """
        Key may be a multiline string (e.g. in the case of a public key), so to
        be able to set it from env, we set it as a base64 encoded string and
        decode it here.
        """
        if self.decode_key is None:
            self.decode_key = b64decode(self.decode_key_b64).decode("utf-8")


@dataclass
class JWTSettingsOIDC(JWTSettingsBase):
    pass


@dataclass(frozen=True)
class AuthConfig(Configuration):
    """Configuration for the authentication of users to the server."""

    auth_type: AuthType = field(
        default=AuthType.NOOP,
        metadata=FieldMetadata(
            description="The type of authentication to use, must be one of: "
            "'noop', 'jwt_local', 'jwt_oidc'.",
            env_vars=["SEMA4AI_AGENT_SERVER_AUTH_TYPE", "AUTH_TYPE"],
        ),
    )
    jwt_settings: JWTSettingsLocal | JWTSettingsOIDC | None = field(
        default=None,
        metadata=FieldMetadata(
            description="The settings for JWT authentication.",
        ),
    )
