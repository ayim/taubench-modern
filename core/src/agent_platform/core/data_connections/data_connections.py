from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from typing import Any, Literal

from agent_platform.core.payloads.data_connection import (
    BigqueryDataConnection,
    BigqueryDataConnectionConfiguration,
    ConfluenceDataConnection,
    ConfluenceDataConnectionConfiguration,
    DataConnectionConfiguration,
    MSSQLDataConnection,
    MSSQLDataConnectionConfiguration,
    MySQLDataConnection,
    MySQLDataConnectionConfiguration,
    OracleDataConnection,
    OracleDataConnectionConfiguration,
    PgvectorDataConnection,
    PgvectorDataConnectionConfiguration,
    PostgresDataConnection,
    PostgresDataConnectionConfiguration,
    RedshiftDataConnection,
    RedshiftDataConnectionConfiguration,
    SalesforceDataConnection,
    SalesforceDataConnectionConfiguration,
    SemaknowledgebaseDataConnection,
    SemaknowledgebaseDataConnectionConfiguration,
    SlackDataConnection,
    SlackDataConnectionConfiguration,
    SnowflakeCustomKeyPairConfiguration,
    SnowflakeDataConnection,
    SnowflakeDataConnectionConfiguration,
    SnowflakeLinkedConfiguration,
    SQLiteDataConnection,
    SQLiteDataConnectionConfiguration,
    TimescaleDBDataConnection,
    TimescaledbDataConnectionConfiguration,
)
from agent_platform.core.payloads.data_connection import (
    DataConnection as PayloadDataConnection,
)


def _serialize_config_to_dict(config: DataConnectionConfiguration) -> dict[str, Any]:
    """Convert configuration to dictionary with proper enum serialization."""
    config_dict = asdict(config)

    # Convert any enum values to their string representations
    for field_info in fields(config):
        field_name = field_info.name
        if field_name in config_dict and config_dict[field_name] is not None:
            value = config_dict[field_name]
            if hasattr(value, "value"):  # Check if it's an enum
                config_dict[field_name] = value.value

    return config_dict


@dataclass(frozen=True)
class DataConnection:
    """Data connection class for storing data connections in the database."""

    id: str = field(
        metadata={
            "description": "The unique identifier of the data connection",
        },
    )
    """The unique identifier of the data connection"""

    name: str = field(
        metadata={
            "description": "The name of the data connection",
        },
    )
    """The name of the data connection"""

    description: str = field(
        metadata={
            "description": "The description of the data connection",
        },
    )
    """The description of the data connection"""

    engine: str = field(
        metadata={
            "description": "The engine type of the data connection",
        },
    )
    """The engine type of the data connection"""

    configuration: DataConnectionConfiguration = field(
        metadata={
            "description": "The configuration parameters for the data connection",
        },
    )
    """The configuration parameters for the data connection"""

    external_id: str | None = field(
        default=None,
        metadata={
            "description": "The external identifier of the data connection",
        },
    )
    """The external identifier of the data connection"""

    created_at: str | None = field(
        default=None,
        metadata={
            "description": "The timestamp when the data connection was created",
        },
    )
    """The timestamp when the data connection was created"""

    updated_at: str | None = field(
        default=None,
        metadata={
            "description": "The timestamp when the data connection was last updated",
        },
    )
    """The timestamp when the data connection was last updated"""

    tags: list[str] = field(
        default_factory=list,
        metadata={
            "description": "The tags for categorizing the data connection",
        },
    )
    """The tags for categorizing the data connection"""

    @classmethod
    def model_validate(cls, data: dict[str, Any]) -> DataConnection:
        """Validate and create a DataConnection from a dictionary."""

        required_fields = ["id", "name", "description", "engine", "configuration"]
        for field_name in required_fields:
            if field_name not in data:
                raise ValueError(f"Missing required field: {field_name}")

        # Parse configuration based on engine type
        configuration = cls._parse_configuration(data["engine"], data["configuration"])

        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            description=str(data["description"]),
            engine=str(data["engine"]),
            configuration=configuration,
            external_id=str(data["external_id"]) if data.get("external_id") is not None else None,
            created_at=data.get("created_at"),
            updated_at=data.get("updated_at"),
            tags=data.get("tags", []),
        )

    @classmethod
    def _parse_configuration(
        cls, engine: str, config_data: dict[str, Any]
    ) -> DataConnectionConfiguration:
        """Parse configuration data into the appropriate configuration type based on engine."""
        return cls._get_engine_parser(engine)(config_data)

    @classmethod
    def _get_engine_parser(cls, engine: str):
        """Get the appropriate parser function for the given engine."""
        parsers = {
            "postgres": cls._parse_postgres_config,
            "redshift": cls._parse_redshift_config,
            "snowflake": cls._parse_snowflake_config,
            "confluence": cls._parse_confluence_config,
            "mysql": cls._parse_mysql_config,
            "mssql": cls._parse_mssql_config,
            "oracle": cls._parse_oracle_config,
            "slack": cls._parse_slack_config,
            "salesforce": cls._parse_salesforce_config,
            "timescaledb": cls._parse_timescaledb_config,
            "pgvector": cls._parse_pgvector_config,
            "bigquery": cls._parse_bigquery_config,
            "sema4_knowledge_base": cls._parse_sema4_knowledge_base_config,
            "sqlite": cls._parse_sqlite_config,
        }
        if engine not in parsers:
            raise ValueError(f"Unsupported engine type: {engine}")
        return parsers[engine]

    @classmethod
    def _parse_sqlite_config(cls, config_data: dict[str, Any]) -> SQLiteDataConnectionConfiguration:
        """Parse SQLite configuration."""
        return SQLiteDataConnectionConfiguration(**config_data)

    @classmethod
    def _parse_postgres_config(
        cls, config_data: dict[str, Any]
    ) -> PostgresDataConnectionConfiguration:
        """Parse PostgreSQL configuration."""
        return cls._parse_ssl_config(config_data, PostgresDataConnectionConfiguration)

    @classmethod
    def _parse_redshift_config(
        cls, config_data: dict[str, Any]
    ) -> RedshiftDataConnectionConfiguration:
        """Parse Redshift configuration."""
        return cls._parse_ssl_config(config_data, RedshiftDataConnectionConfiguration)

    @classmethod
    def _parse_pgvector_config(
        cls, config_data: dict[str, Any]
    ) -> PgvectorDataConnectionConfiguration:
        """Parse Pgvector configuration."""
        return cls._parse_ssl_config(config_data, PgvectorDataConnectionConfiguration)

    @classmethod
    def _parse_ssl_config(cls, config_data: dict[str, Any], config_class):
        """Parse configuration with SSL mode conversion."""
        if "sslmode" in config_data and isinstance(config_data["sslmode"], str):
            from agent_platform.core.payloads.data_connection import Sslmode

            config_data = config_data.copy()
            config_data["sslmode"] = Sslmode(config_data["sslmode"])
        return config_class(**config_data)

    @classmethod
    def _parse_snowflake_config(cls, config_data: dict[str, Any]) -> DataConnectionConfiguration:
        """Parse Snowflake configuration."""
        credential_type = config_data.get("credential_type", "linked")
        if credential_type == "linked":
            return SnowflakeLinkedConfiguration(**config_data)
        if credential_type == "custom-key-pair":
            return SnowflakeCustomKeyPairConfiguration(**config_data)
        return SnowflakeDataConnectionConfiguration(**config_data)

    @classmethod
    def _parse_confluence_config(
        cls, config_data: dict[str, Any]
    ) -> ConfluenceDataConnectionConfiguration:
        """Parse Confluence configuration."""
        return ConfluenceDataConnectionConfiguration(**config_data)

    @classmethod
    def _parse_mysql_config(cls, config_data: dict[str, Any]) -> MySQLDataConnectionConfiguration:
        """Parse MySQL configuration."""
        return MySQLDataConnectionConfiguration(**config_data)

    @classmethod
    def _parse_mssql_config(cls, config_data: dict[str, Any]) -> MSSQLDataConnectionConfiguration:
        """Parse MSSQL configuration."""
        return MSSQLDataConnectionConfiguration(**config_data)

    @classmethod
    def _parse_oracle_config(cls, config_data: dict[str, Any]) -> OracleDataConnectionConfiguration:
        """Parse Oracle configuration."""
        return OracleDataConnectionConfiguration(**config_data)

    @classmethod
    def _parse_slack_config(cls, config_data: dict[str, Any]) -> SlackDataConnectionConfiguration:
        """Parse Slack configuration."""
        return SlackDataConnectionConfiguration(**config_data)

    @classmethod
    def _parse_salesforce_config(
        cls, config_data: dict[str, Any]
    ) -> SalesforceDataConnectionConfiguration:
        """Parse Salesforce configuration."""
        return SalesforceDataConnectionConfiguration(**config_data)

    @classmethod
    def _parse_timescaledb_config(
        cls, config_data: dict[str, Any]
    ) -> TimescaledbDataConnectionConfiguration:
        """Parse TimescaleDB configuration."""
        return TimescaledbDataConnectionConfiguration(**config_data)

    @classmethod
    def _parse_bigquery_config(
        cls, config_data: dict[str, Any]
    ) -> BigqueryDataConnectionConfiguration:
        """Parse BigQuery configuration."""
        return BigqueryDataConnectionConfiguration(**config_data)

    @classmethod
    def _parse_sema4_knowledge_base_config(
        cls, config_data: dict[str, Any]
    ) -> SemaknowledgebaseDataConnectionConfiguration:
        """Parse Sema4 Knowledge Base configuration."""
        return SemaknowledgebaseDataConnectionConfiguration(**config_data)

    def model_dump(self, *, mode: Literal["python", "json"] = "python") -> dict:
        """Convert the DataConnection to a dictionary."""
        # Convert configuration to dict with proper enum serialization
        if hasattr(self.configuration, "__dataclass_fields__"):
            config_dict = _serialize_config_to_dict(self.configuration)
        else:
            config_dict = self.configuration

        result = {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "engine": self.engine,
            "configuration": config_dict,
            "tags": self.tags,
        }

        if self.external_id is not None:
            result["external_id"] = self.external_id

        if self.created_at is not None:
            result["created_at"] = self.created_at
        if self.updated_at is not None:
            result["updated_at"] = self.updated_at

        if mode == "json" and isinstance(config_dict, dict) and "password" in config_dict:
            result["configuration"] = dict(config_dict)
            result["configuration"]["password"] = "<REDACTED>"

        return result

    def to_payload(self) -> PayloadDataConnection:
        """Convert to payload DataConnection object"""
        from datetime import datetime

        # Convert string timestamps to datetime objects if they exist, otherwise use current time
        created_at = datetime.now()
        updated_at = datetime.now()

        if self.created_at:
            if isinstance(self.created_at, str):
                created_at = datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
            else:
                created_at = self.created_at
        if self.updated_at:
            if isinstance(self.updated_at, str):
                updated_at = datetime.fromisoformat(self.updated_at.replace("Z", "+00:00"))
            else:
                updated_at = self.updated_at

        # Direct conversion based on engine type
        engine_mapping = {
            "postgres": PostgresDataConnection,
            "redshift": RedshiftDataConnection,
            "confluence": ConfluenceDataConnection,
            "mysql": MySQLDataConnection,
            "mssql": MSSQLDataConnection,
            "oracle": OracleDataConnection,
            "slack": SlackDataConnection,
            "salesforce": SalesforceDataConnection,
            "timescaledb": TimescaleDBDataConnection,
            "pgvector": PgvectorDataConnection,
            "bigquery": BigqueryDataConnection,
            "sema4_knowledge_base": SemaknowledgebaseDataConnection,
            "sqlite": SQLiteDataConnection,
        }

        if self.engine == "snowflake":
            # Type assertion: when engine is snowflake, configuration must be a Snowflake config
            snowflake_config = self.configuration
            assert isinstance(
                snowflake_config,
                SnowflakeLinkedConfiguration
                | SnowflakeCustomKeyPairConfiguration
                | SnowflakeDataConnectionConfiguration,
            ), f"Expected Snowflake configuration type, got {type(snowflake_config)}"
            return SnowflakeDataConnection(
                name=self.name,
                description=self.description,
                id=self.id,
                external_id=self.external_id,
                engine="snowflake",
                configuration=snowflake_config,
                created_at=created_at,
                updated_at=updated_at,
                tags=self.tags,
            )

        if self.engine in engine_mapping:
            connection_class = engine_mapping[self.engine]
            return connection_class(
                name=self.name,
                description=self.description,
                id=self.id,
                external_id=self.external_id,
                engine=self.engine,
                configuration=self.configuration,
                created_at=created_at,
                updated_at=updated_at,
                tags=self.tags,
            )

        raise ValueError(f"Unsupported engine type: {self.engine}")

    def build_mindsdb_parameters(self) -> str:
        """Generates the body of the PARAMETERS clause for a MindsDB data source"""
        config_dict = _serialize_config_to_dict(self.configuration)

        # Ensure port is an integer to avoid "invalid integer value" errors
        if "port" in config_dict and isinstance(config_dict["port"], float):
            config_dict["port"] = int(config_dict["port"])

        return json.dumps(config_dict).lstrip("{").rstrip("}")

    @classmethod
    def from_payload(cls, payload: PayloadDataConnection, connection_id: str) -> DataConnection:
        """Create DataConnection directly from PayloadDataConnection."""
        if payload.configuration is None:
            raise ValueError("DataConnection configuration cannot be None")

        return cls(
            id=connection_id,
            name=payload.name,
            description=payload.description,
            engine=payload.engine,
            configuration=payload.configuration,
            external_id=payload.external_id,
            tags=payload.tags,
        )
