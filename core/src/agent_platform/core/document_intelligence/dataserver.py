from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from agent_platform.core.document_intelligence.data_connection import DataConnection
from agent_platform.core.utils import SecretString


class DIDSConnectionKind(StrEnum):
    """The kind of connection to the Document Intelligence Data Server"""

    HTTP = "http"
    MYSQL = "mysql"


@dataclass(frozen=True)
class DIDSApiConnectionDetails:
    """DIDSApiConnectionDetails is a class that represents the details needed to
    connect to the Document Intelligence Data Server"""

    host: str = field(
        metadata={
            "description": "The host address of the Document Intelligence Data Server",
        },
    )
    """The host address of the Document Intelligence Data Server"""

    port: int = field(
        metadata={
            "description": "The port of this connection to the Document Intelligence Data Server",
        },
    )
    """The port of this connection to the Document Intelligence Data Server"""

    kind: DIDSConnectionKind = field(
        default=DIDSConnectionKind.HTTP,
        metadata={
            "description": "The kind of connection to the Document Intelligence Data Server",
        },
    )
    """The kind of connection to the Document Intelligence Data Server"""

    def __post_init__(self):
        # Ensure kind is the proper type
        if not isinstance(self.kind, DIDSConnectionKind):
            object.__setattr__(self, "kind", DIDSConnectionKind(self.kind))

        # Validate host is not empty or whitespace-only
        if not self.host or not self.host.strip():
            raise ValueError("Host cannot be empty")

        # Validate port is positive
        if self.port <= 0:
            raise ValueError("Port must be a positive integer")

    @property
    def full_address(self) -> str:
        """The full address of the Document Intelligence Data Server"""
        return f"{self.host}:{self.port}"

    def model_dump(self, *, mode: Literal["python", "json"] = "python") -> dict:
        """Convert the DIDSConnectionDetails to a dictionary

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
        data: "dict[str, Any] | Mapping[str, Any] | DIDSApiConnectionDetails",
    ) -> "DIDSApiConnectionDetails":
        """Create a DIDSConnectionDetails instance from a dictionary or existing instance.

        Args:
            data: Dictionary containing kind, host, and port fields,
                  or an existing DIDSApiConnectionDetails instance

        Returns:
            A DIDSConnectionDetails instance
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
class DIDSConnectionDetails:
    """DIDSConnectionDetails contains authentication information for connecting to DIDS"""

    username: str | None = field(
        metadata={
            "description": "The username to connect to the Document Intelligence Data Server",
        },
    )
    """The username to connect to the Document Intelligence Data Server"""

    password: SecretString | None = field(
        metadata={
            "description": "The password to connect to the Document Intelligence Data Server",
        },
    )
    """The password to connect to the Document Intelligence Data Server"""

    data_server_connections: list[DIDSApiConnectionDetails] = field(
        metadata={
            "description": "The connection details for the Document Intelligence Data Server",
        },
    )
    """The connection details for the Document Intelligence Data Server"""

    updated_at: datetime = field(
        default_factory=datetime.now,
        metadata={
            "description": "The timestamp when the connection details were last updated",
        },
    )
    """The timestamp when the connection details were last updated"""

    data_connections: list[DataConnection] = field(
        default_factory=list,
        metadata={
            "description": "The data connections for the Document Intelligence Data Server",
        },
    )
    """The data connections for the Document Intelligence Data Server"""

    def __post_init__(self):
        if isinstance(self.password, str):
            object.__setattr__(self, "password", SecretString(self.password))

    def as_datasource_connection_input(self) -> dict:
        """Convert the DIDSConnectionDetails to a datasource connection input dictionary"""
        result = {}

        for connection in self.data_server_connections:
            base_connection = {
                "host": connection.host,
                "port": connection.port,
                "user": self.username,
                "password": self.password.get_secret_value() if self.password else None,
            }

            # As http requires a different key name, we cannot just iterate over the connections
            # and add them to the result dictionary.
            if connection.kind == DIDSConnectionKind.HTTP:
                result["http"] = {
                    "url": connection.full_address,
                    **base_connection,
                }
                result["http"].pop("host")  # Remove host as it is already in the url
            elif connection.kind == DIDSConnectionKind.MYSQL:
                result["mysql"] = base_connection
            # Note: Skip unknown connection kinds rather than defaulting

        return result

    def model_dump(self, *, mode: Literal["python", "json"] = "python") -> dict:
        """Convert the DIDSConnectionDetails to a dictionary

        Args:
            mode: Either 'python' for Python objects or 'json' for JSON-serializable values
        """
        if mode == "python":
            password_value = self.password
        elif self.password is not None:
            password_value = self.password.get_secret_value()
        else:
            password_value = None

        return {
            "username": self.username,
            "password": password_value,
            "data_server_connections": [
                conn.model_dump(mode=mode) for conn in self.data_server_connections
            ],
            "updated_at": self.updated_at if mode == "python" else self.updated_at.isoformat(),
            "data_connections": [conn.model_dump(mode=mode) for conn in self.data_connections],
        }

    @classmethod
    def model_validate(
        cls, data: "dict[str, Any] | Mapping[str, Any] | DIDSConnectionDetails"
    ) -> "DIDSConnectionDetails":
        """Create a DIDSConnectionDetails instance from a dictionary or existing instance.

        Args:
            data: Dictionary containing username, password, connections,
                  and optional updated_at fields, or an existing DIDSConnectionDetails instance

        Returns:
            A DIDSConnectionDetails instance
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

        # Handle nested connections list
        if "data_server_connections" in data_dict and isinstance(
            data_dict["data_server_connections"], list
        ):
            data_dict["data_server_connections"] = [
                DIDSApiConnectionDetails.model_validate(conn)
                for conn in data_dict["data_server_connections"]
            ]

        if "data_connections" in data_dict and isinstance(data_dict["data_connections"], list):
            data_dict["data_connections"] = [
                DataConnection.model_validate(conn) for conn in data_dict["data_connections"]
            ]

        # Handle SecretString conversion (password can be a string or already a SecretString)
        if "password" in data_dict and isinstance(data_dict["password"], str):
            data_dict["password"] = SecretString(data_dict["password"])

        # Handle datetime parsing from ISO string
        if "updated_at" in data_dict and isinstance(data_dict["updated_at"], str):
            data_dict["updated_at"] = datetime.fromisoformat(data_dict["updated_at"])

        return cls(**data_dict)
