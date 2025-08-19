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
    """An engine for a data connection to the Document Intelligence Data Server"""

    # TODO what are all of the engines we currently support? Do we need to enumerate
    # them? Just allow pass-through?
    POSTGRES = "postgres"


@dataclass(frozen=True)
class DataConnection:
    """A data connection to the Document Intelligence Data Server"""

    id: str = field(
        metadata={
            "description": "The ID of the data connection",
        },
    )
    """The ID of the data connection"""

    name: str = field(
        metadata={
            "description": "The name of the data connection",
        },
    )
    """The name of the data connection"""

    engine: DataConnectionEngine = field(
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

    @classmethod
    def model_validate(cls, data: dict[str, Any]) -> "DataConnection":
        """Validate and create a DataConnection from a dictionary"""
        match data["engine"]:
            case DataConnectionEngine.POSTGRES:
                for key in ["user", "password", "host", "port", "database"]:
                    if key not in data["configuration"]:
                        raise MissingDataConnectionDetailsError(DataConnectionEngine.POSTGRES, key)
            case _:
                raise UnsupportedDataConnectionEngineError(data["engine"])

        return cls(**data)

    def model_dump(self, *, mode: Literal["python", "json"] = "python") -> dict:
        """Convert the DataConnection to a dictionary"""
        # Redact password in JSON mode
        if mode == "json" and "password" in self.configuration:
            self.configuration["password"] = "<REDACTED>"

        return {
            "id": self.id,
            "name": self.name,
            "engine": self.engine,
            "configuration": self.configuration,
        }

    def build_mindsdb_parameters(self) -> str:
        """Generates the body of the PARAMETERS clause for a MindsDB data source"""
        params = []
        for key, value in self.configuration.items():
            if isinstance(value, int):
                params.append(f'"{key}": {value}')
            else:
                params.append(f'"{key}": "{value}"')
        return ", \n".join(params)
