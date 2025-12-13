"""Data sources using the new unified DataConnection type."""

from dataclasses import dataclass, field
from typing import Literal

from agent_platform.core.data_connections.data_connections import DataConnection
from agent_platform.core.data_server.data_server import DataServerDetails


@dataclass(frozen=True)
class DataSources:
    """
    The encapsulation of data sources on a Data Server using the new unified DataConnection type.
    """

    data_server: DataServerDetails = field(
        metadata={
            "description": "The Data Server to which the Data Sources should be created",
        },
    )
    data_sources: dict[str, DataConnection] = field(
        metadata={
            "description": "A mapping of Data Source names to Data Connections",
        },
    )
    """The Data Sources which should be created on the Data Server"""

    def model_dump(self, *, mode: Literal["python", "json"] = "python") -> dict:
        return {
            "data_server": self.data_server.model_dump(mode=mode),
            "data_sources": {name: conn.model_dump() for name, conn in self.data_sources.items()},
        }

    @classmethod
    def model_validate(cls, data: dict) -> "DataSources":
        return DataSources(
            data_server=DataServerDetails.model_validate(data["data_server"]),
            data_sources={name: DataConnection.model_validate(conn) for name, conn in data["data_sources"].items()},
        )
