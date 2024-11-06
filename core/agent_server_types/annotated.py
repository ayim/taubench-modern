from typing import Annotated
from uuid import UUID

from pydantic import (
    BeforeValidator,
    SecretStr,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    WrapSerializer,
)


def ser_secret_str(
    value: SecretStr, nxt: SerializerFunctionWrapHandler, info: SerializationInfo
) -> str:
    """Serializer function which unmasks secret strings if the context's "raw"
    key is set to True. Context must be a dict-like object."""
    if info.context is not None and info.context.get("raw", False):
        return value.get_secret_value()
    else:
        return nxt(value, info)


SerializableSecretStr = Annotated[SecretStr, WrapSerializer(ser_secret_str)]

StrWithUuidInput = Annotated[
    str, BeforeValidator(lambda v: str(v) if isinstance(v, UUID) else v)
]
