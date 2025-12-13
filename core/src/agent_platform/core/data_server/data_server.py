from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from agent_platform.core.data_server.data_connection import DataConnection
from agent_platform.core.utils import SecretString


class DataServerEndpointKind(StrEnum):
    """The protocol to the Data Server"""

    HTTP = "http"
    MYSQL = "mysql"


@dataclass(frozen=True)
class DataServerEndpoint:
    """DataServerEndpoint is a class that represents the details needed to
    connect to a Data Server over a specific protocol"""

    host: str = field(
        metadata={
            "description": "The host address of the Data Server",
        },
    )
    """The host address of the Data Server"""

    port: int = field(
        metadata={
            "description": "The port of this connection to the Data Server",
        },
    )
    """The port of this connection to the Data Server"""

    kind: DataServerEndpointKind = field(
        default=DataServerEndpointKind.HTTP,
        metadata={
            "description": "The kind of connection to the Data Server",
        },
    )
    """The kind of connection to the Data Server"""

    def __post_init__(self):
        # Ensure kind is the proper type
        if not isinstance(self.kind, DataServerEndpointKind):
            object.__setattr__(self, "kind", DataServerEndpointKind(self.kind))

        # Validate host is not empty or whitespace-only
        if not self.host or not self.host.strip():
            raise ValueError("Host cannot be empty")

        # Validate port is positive
        if self.port <= 0:
            raise ValueError("Port must be a positive integer")

    @property
    def full_address(self) -> str:
        """The full address of the Data Server"""
        return f"{self.host}:{self.port}"

    def model_dump(self, *, mode: Literal["python", "json"] = "python") -> dict:
        """Convert the DataServerEndpointDetails to a dictionary

        Args:
            mode: Either 'python' for Python objects or 'json' for JSON-serializable values
        """
        return {
            "kind": self.kind.value if mode == "json" else self.kind,
            "host": self.host,
            "port": self.port,
        }

    @classmethod
    def model_validate(
        cls,
        data: "dict[str, Any] | Mapping[str, Any] | DataServerEndpoint",
    ) -> "DataServerEndpoint":
        """Create a DataServerEndpoint instance from a dictionary or existing instance.

        Args:
            data: Dictionary containing kind, host, and port fields,
                  or an existing DataServerEndpoint instance

        Returns:
            A DataServerEndpoint instance
        """
        # If it's already an instance of the class, return it directly
        if isinstance(data, cls):
            return data

        # Convert to dict if needed
        data_dict: dict[str, Any]
        if isinstance(data, dict):
            data_dict = data
        elif hasattr(data, "items"):
            # Handle mapping-like objects
            data_dict = dict(data.items())  # type: ignore[arg-type]
        elif hasattr(data, "__dict__"):
            # Handle dataclass or other objects with __dict__
            data_dict = dict(data.__dict__)
        else:
            # Fallback: try to convert directly
            try:
                data_dict = dict(data)  # type: ignore[assignment]
            except (TypeError, ValueError) as err:
                raise TypeError(f"Cannot convert {type(data)} to dict for model_validate") from err

        return cls(**data_dict)


@dataclass(frozen=True)
class DataServerDetails:
    """DataServerDetails contains credentials to a DataServer"""

    username: str | None = field(
        metadata={
            "description": "The username to connect to the Data Server",
        },
    )
    """The username to connect to the Data Server"""

    password: str | SecretString | None = field(
        metadata={
            "description": "The password to connect to a Data Server",
        },
    )
    """The password to connect to the Data Server"""

    data_server_endpoints: list[DataServerEndpoint] = field(
        metadata={
            "description": "The connection details for a Data Server",
        },
    )
    """The connection details for the Data Server"""

    updated_at: datetime = field(
        default_factory=datetime.now,
        metadata={
            "description": "The timestamp when the connection details were last updated",
        },
    )
    """The timestamp when the connection details were last updated"""

    def __post_init__(self):
        if isinstance(self.password, str):
            object.__setattr__(self, "password", SecretString(self.password))

    @property
    def password_str(self) -> str | None:
        """Get the password as a string, regardless of its internal representation.

        Returns:
            The password as a string, or None if no password is set.
        """
        if self.password is None:
            return None
        if isinstance(self.password, SecretString):
            return self.password.get_secret_value()
        return self.password

    def as_datasource_connection_input(self) -> dict:
        """Convert the DataServerDetails to a datasource connection input dictionary"""
        result = {}

        for endpoint in self.data_server_endpoints:
            base_connection = {
                "host": endpoint.host,
                "port": endpoint.port,
                "user": self.username,
                "password": self.password_str,
            }

            # As http requires a different key name, we cannot just iterate over the connections
            # and add them to the result dictionary.
            match endpoint.kind:
                case DataServerEndpointKind.HTTP:
                    result["http"] = {
                        "url": f"http://{endpoint.full_address}",
                        **base_connection,
                    }
                    result["http"].pop("host")  # Remove host as it is already in the url
                case DataServerEndpointKind.MYSQL:
                    result["mysql"] = base_connection
                case _:
                    pass  # Skip unknown connection kinds

        return result

    def model_dump(self, *, mode: Literal["python", "json"] = "python") -> dict:
        """Convert the DataServerDetails to a dictionary

        Args:
            mode: Either 'python' for Python objects or 'json' for JSON-serializable values
        """
        if mode == "python":
            password_value = self.password
        elif self.password is not None:
            # in mode=json, unwrap the SecretString
            password_value = self.password_str
        else:
            password_value = None

        return {
            "username": self.username,
            "password": password_value,
            "data_server_endpoints": [conn.model_dump(mode=mode) for conn in self.data_server_endpoints],
            "updated_at": self.updated_at if mode == "python" else self.updated_at.isoformat(),
        }

    @classmethod
    def model_validate(cls, data: "dict[str, Any] | Mapping[str, Any] | DataServerDetails") -> "DataServerDetails":
        """Create a DataServerDetails instance from a dictionary or existing instance.

        Args:
            data: Dictionary containing username, password, connections,
                  and optional updated_at fields, or an existing DataServerDetails instance

        Returns:
            A DataServerDetails instance
        """
        # If it's already an instance of the class, return it directly
        if isinstance(data, cls):
            return data

        # Convert to dict if needed
        data_dict: dict[str, Any]
        if isinstance(data, dict):
            data_dict = data.copy()
        elif hasattr(data, "items"):
            # Handle mapping-like objects
            data_dict = dict(data.items())  # type: ignore[arg-type]
        elif hasattr(data, "__dict__"):
            # Handle dataclass or other objects with __dict__
            data_dict = dict(data.__dict__)
        else:
            # Fallback: try to convert directly
            try:
                data_dict = dict(data)  # type: ignore[assignment]
            except (TypeError, ValueError) as err:
                raise TypeError(f"Cannot convert {type(data)} to dict for model_validate") from err

        # Serialize the list of data server API endpoitns.
        # Handle the old name for backwards compatibility as these are in the DB.
        for key in ["data_server_endpoints", "data_server_connections", "endpoints"]:
            if key in data_dict and isinstance(data_dict[key], list):
                data_dict["data_server_endpoints"] = [
                    DataServerEndpoint.model_validate(conn) for conn in data_dict[key]
                ]
                break
        # Remove the old name if present
        if "data_server_connections" in data_dict:
            del data_dict["data_server_connections"]
        if "endpoints" in data_dict:
            del data_dict["endpoints"]

        # Serialize the list of data sources.
        # Handle the old name for backwards compatibility as these are in the DB.
        for key in ["data_sources", "data_connections"]:
            if key in data_dict and isinstance(data_dict[key], dict):
                data_dict["data_sources"] = {
                    name: DataConnection.model_validate(conn) for name, conn in data_dict[key].items()
                }
                break
        # Remove the old name if present
        if "data_connections" in data_dict:
            del data_dict["data_connections"]

        # Handle SecretString conversion (password can be a string or already a SecretString)
        if "password" in data_dict and isinstance(data_dict["password"], str):
            data_dict["password"] = SecretString(data_dict["password"])

        # Handle datetime parsing from ISO string
        if "updated_at" in data_dict and isinstance(data_dict["updated_at"], str):
            data_dict["updated_at"] = datetime.fromisoformat(data_dict["updated_at"])

        return cls(**data_dict)
