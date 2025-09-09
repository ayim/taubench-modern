import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal

from agent_platform.core.errors.base import PlatformHTTPError
from agent_platform.core.errors.responses import ErrorCode


class UnsupportedDataConnectionEngineError(PlatformHTTPError):
    """An error raised when an unsupported data connection engine is encountered"""

    def __init__(self, engine: str):
        super().__init__(
            message=f"Unsupported data connection engine: {engine}",
            error_code=ErrorCode.BAD_REQUEST,
        )


class MissingDataConnectionDetailsError(PlatformHTTPError):
    """An error raised when required data connection details are missing"""

    def __init__(self, engine: str, missing_key: str):
        super().__init__(
            message=f"Missing required configuration key for {engine}: {missing_key}",
            error_code=ErrorCode.BAD_REQUEST,
        )


class DataConnectionEngine(StrEnum):
    """The non-exhaustive list of engines for a data connection to the Data Server.
    We have validation logic of the configuration for each specified engine."""

    POSTGRES = "postgres"


@dataclass(frozen=True)
class DataConnection:
    """A data connection to the Document Intelligence Data Server"""

    name: str = field(
        metadata={
            "description": "The name of the data connection",
        },
    )
    """The name of the data connection"""

    engine: str = field(
        metadata={
            "description": "The engine of the data connection",
        },
    )
    """The engine of the data connection"""

    configuration: dict[str, Any] = field(
        metadata={
            "description": "The configuration of the data connection",
        },
    )
    """The configuration of the data connection"""

    external_id: str | None = field(
        default=None,
        metadata={
            "description": "The ID of the data connection",
        },
    )
    """The ID of the data connection"""

    id: str | None = field(
        default=None,
        metadata={
            "description": "The ID of the data connection (deprecated, use external_id instead)",
            "deprecated": True,
        },
    )
    """The ID of the data connection (deprecated, use external_id instead)"""

    @classmethod
    def model_validate(cls, data: dict[str, Any]) -> "DataConnection":
        """Validate and create a DataConnection from a dictionary"""
        # Use id as fallback for external_id if external_id is not provided
        data["external_id"] = data.get("external_id") or data.get("id")
        data.pop("id", None)
        match data["engine"]:
            case DataConnectionEngine.POSTGRES.value:
                for key in ["user", "password", "host", "port", "database"]:
                    if key not in data["configuration"]:
                        raise MissingDataConnectionDetailsError(DataConnectionEngine.POSTGRES, key)
            case _:
                # TODO Add more engine types here as we want to enhance our validation checks
                # over the database config.
                pass

        return cls(**data)

    def model_dump(self, *, mode: Literal["python", "json"] = "python") -> dict:
        """Convert the DataConnection to a dictionary"""
        # Redact password in JSON mode
        if mode == "json" and "password" in self.configuration:
            self.configuration["password"] = "<REDACTED>"

        return {
            "external_id": self.external_id,
            "name": self.name,
            "engine": self.engine,
            "configuration": self.configuration,
        }

    def build_mindsdb_parameters(self) -> str:
        """Generates the body of the PARAMETERS clause for a MindsDB data source"""
        return json.dumps(self.configuration).lstrip("{").rstrip("}")
