from dataclasses import dataclass
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Discriminator, TypeAdapter


# Base class for all MCP variable types
class MCPVariableBase(BaseModel):
    type: str


class MCPVariableTypeString(MCPVariableBase):
    type: Literal["string"] = "string"
    description: str | None = None
    value: str | None = None


class MCPVariableTypeSecret(MCPVariableBase):
    type: Literal["secret"] = "secret"
    description: str | None = None
    value: str | None = None


class MCPVariableTypeOAuth2Secret(MCPVariableBase):
    type: Literal["oauth2-secret"] = "oauth2-secret"
    provider: str
    scopes: list[str]
    description: str | None = None
    value: str | None = None


class MCPVariableTypeDataServerInfo(MCPVariableBase):
    type: Literal["data-server-info"] = "data-server-info"
    value: str | None = None


# Discriminated union for MCP variable types (excluding plain str)
MCPDiscriminatedUnion = Annotated[
    MCPVariableTypeString
    | MCPVariableTypeSecret
    | MCPVariableTypeOAuth2Secret
    | MCPVariableTypeDataServerInfo,
    Discriminator("type"),
]

# TypeAdapter for discriminated union
MCPVariableAdapter = TypeAdapter(MCPDiscriminatedUnion)

# Full union including plain str
MCPUnionOfVariableTypes = str | MCPDiscriminatedUnion
MCPVariables = dict[str, MCPUnionOfVariableTypes]


def _parse_mcp_variable(data: Any) -> MCPDiscriminatedUnion | str:
    if isinstance(data, str):
        return data
    try:
        return MCPVariableAdapter.validate_python(data)
    except Exception:
        # fallback: return as string
        return str(data)


def serialize_mcp_variables(
    variables: MCPVariables | None,
    exclude_none: bool = True,
) -> dict[str, Any] | None:
    """Serialize MCPVariables to a JSON-serializable dictionary."""
    if variables is None:
        return None
    result = {}
    for key, value in variables.items():
        if isinstance(value, str):
            result[key] = value
        elif isinstance(value, BaseModel):
            result[key] = value.model_dump(exclude_none=exclude_none)
        else:
            result[key] = str(value)
    return result


def deserialize_mcp_variable(data: Any) -> MCPUnionOfVariableTypes:
    return _parse_mcp_variable(data)


def deserialize_mcp_variables(variables: dict[str, Any] | None) -> MCPVariables | None:
    if variables is None:
        return None
    return {k: deserialize_mcp_variable(v) for k, v in variables.items()}


@dataclass(frozen=True)
class MCPToolDetail:
    name: str


@dataclass(frozen=True)
class MCPServerDetail:
    name: str
    actions: list[MCPToolDetail]
    status: Literal["online", "offline"]
