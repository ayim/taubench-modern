from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class MCPVariableTypeString:
    type: Literal["string"] = field(init=False, default="string")
    description: str | None = None
    default: str | None = None
    value: str | None = None  # the literal value inputted by the user

    def model_dump(self) -> dict:
        """Serializes the MCP variable to a dictionary. Useful for JSON serialization."""
        result = {"type": self.type}
        if self.description is not None:
            result["description"] = self.description
        if self.default is not None:
            result["default"] = self.default
        if self.value is not None:
            result["value"] = self.value

        return result


@dataclass(frozen=True)
class MCPVariableTypeSecret:
    type: Literal["secret"] = field(init=False, default="secret")
    description: str | None = None
    value: str | None = None  # the literal value inputted by the user

    def model_dump(self) -> dict:
        """Serializes the MCP variable to a dictionary. Useful for JSON serialization."""
        result = {"type": self.type}
        if self.description is not None:
            result["description"] = self.description
        if self.value is not None:
            result["value"] = self.value

        return result


@dataclass(frozen=True)
class MCPVariableTypeOAuth2Secret:
    type: Literal["oauth2-secret"] = field(init=False, default="oauth2-secret")
    provider: str
    scopes: list[str]
    description: str | None = None
    value: str | None = None  # the literal value inputted by the user

    def model_dump(self) -> dict:
        """Serializes the MCP variable to a dictionary. Useful for JSON serialization."""
        result = {
            "type": self.type,
            "provider": self.provider,
            "scopes": self.scopes,
        }
        if self.description is not None:
            result["description"] = self.description
        if self.value is not None:
            result["value"] = self.value

        return result


@dataclass(frozen=True)
class MCPVariableTypeDataServerInfo:
    type: Literal["data-server-info"] = field(init=False, default="data-server-info")
    value: str | None = None  # the literal value inputted by the user

    def model_dump(self) -> dict:
        """Serializes the MCP variable to a dictionary. Useful for JSON serialization."""
        result = {"type": self.type}
        if self.value is not None:
            result["value"] = self.value

        return result


# Union of all possible MCPVariable types
MCPUnionOfVariableTypes = (
    str
    | MCPVariableTypeOAuth2Secret
    | MCPVariableTypeSecret
    | MCPVariableTypeString
    | MCPVariableTypeDataServerInfo
)


# Mapping from variable to one of the union types
MCPVariables = dict[str, MCPUnionOfVariableTypes]


def serialize_mcp_variables(variables: MCPVariables | None) -> dict[str, Any] | None:
    """Serialize MCPVariables to a JSON-serializable dictionary."""
    if variables is None:
        return None
    result = {}
    for key, value in variables.items():
        if isinstance(value, str):
            result[key] = value
        elif hasattr(value, "model_dump"):
            result[key] = value.model_dump()
        else:
            # Fallback for any other types
            result[key] = str(value)
    return result


def deserialize_mcp_variable(data: Any) -> MCPUnionOfVariableTypes:  # noqa: PLR0911
    """Deserialize a dict into the correct MCPVariableType* dataclass, or return as-is."""
    if isinstance(
        data,
        MCPVariableTypeString
        | MCPVariableTypeSecret
        | MCPVariableTypeOAuth2Secret
        | MCPVariableTypeDataServerInfo,
    ):
        return data
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        match data.get("type"):
            case "string":
                return MCPVariableTypeString(
                    description=data.get("description"),
                    default=data.get("default"),
                    value=data.get("value"),
                )
            case "secret":
                return MCPVariableTypeSecret(
                    description=data.get("description"),
                    value=data.get("value"),
                )
            case "oauth2-secret":
                return MCPVariableTypeOAuth2Secret(
                    provider=data["provider"],
                    scopes=data["scopes"],
                    description=data.get("description"),
                    value=data.get("value"),
                )
            case "data-server-info":
                return MCPVariableTypeDataServerInfo(
                    value=data.get("value"),
                )
    # fallback: return as string to match MCPUnionOfVariableTypes
    return str(data)


def deserialize_mcp_variables(variables: dict[str, Any] | None) -> MCPVariables | None:
    if variables is None:
        return None
    return {k: deserialize_mcp_variable(v) for k, v in variables.items()}
