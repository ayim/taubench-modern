from dataclasses import dataclass, field, fields
from typing import Literal

from agent_platform.core.platforms.base import PlatformParameters
from agent_platform.core.utils import SecretString


@dataclass(frozen=True, kw_only=True)
class CortexPlatformParameters(PlatformParameters):
    """Parameters for the Snowflake Cortex platform.

    This class encapsulates all configuration parameters for Snowflake Cortex
    client initialization.
    """

    kind: Literal["cortex"] = field(
        default="cortex",
        metadata={"description": "The kind of platform parameters."},
        init=False,
    )
    """The kind of platform parameters."""

    snowflake_username: str | None = field(
        default=None,
        metadata={
            "description": "The Snowflake username. Optional, as token-based auth is preferred.",
        },
    )
    """The Snowflake username. Optional, as token-based auth is preferred."""

    snowflake_password: SecretString | None = field(
        default=None,
        metadata={
            "description": "The Snowflake password. Optional, as token-based auth is preferred.",
        },
    )
    """The Snowflake password. Optional, as token-based auth is preferred."""

    snowflake_account: str | None = field(
        default=None,
        metadata={
            "description": "The Snowflake account. If not provided, it will be"
            "inferred from the environment.",
        },
    )
    """The Snowflake account. If not provided,
    it will be inferred from the environment."""

    snowflake_host: str | None = field(
        default=None,
        metadata={
            "description": "The Snowflake host. If not provided, it will be"
            "inferred from the environment (built from account name).",
        },
    )
    """The Snowflake host. If not provided,
    it will be inferred from the environment (built from account name)."""

    snowflake_warehouse: str | None = field(
        default=None,
        metadata={
            "description": "The Snowflake warehouse. Optional.",
        },
    )
    """The Snowflake warehouse. Optional."""

    snowflake_database: str | None = field(
        default=None,
        metadata={
            "description": "The Snowflake database. Optional.",
        },
    )
    """The Snowflake database. Optional."""

    snowflake_schema: str | None = field(
        default=None,
        metadata={
            "description": "The Snowflake schema. Optional.",
        },
    )
    """The Snowflake schema. Optional."""

    snowflake_role: str | None = field(
        default=None,
        metadata={
            "description": "The Snowflake role. Optional.",
        },
    )
    """The Snowflake role. Optional."""

    def __post_init__(self) -> None:
        """Process any extra kwargs as Config parameters after dataclass
        initialization."""
        from os import getenv

        super().__post_init__()

        # Override snowflake_host if SNOWFLAKE_HOST is set (this happens
        # when using SPCS, for example)
        if getenv("SNOWFLAKE_HOST"):
            object.__setattr__(
                self,
                "snowflake_host",
                getenv("SNOWFLAKE_HOST"),
            )

        # If snowflake_host is not set, try to infer it from snowflake_account
        if not self.snowflake_host:
            account = self.snowflake_account or getenv("SNOWFLAKE_ACCOUNT")
            if account:
                object.__setattr__(
                    self,
                    "snowflake_host",
                    f"{account}.snowflakecomputing.com",
                )

        # Replace any underscores with hyphens in the hostname for SSL certificate
        # compliance. According to RFC 1035 (and related standards), underscores are
        # not allowed in hostnames, which can cause SSL certificate validation to fail.
        if self.snowflake_host:
            object.__setattr__(
                self,
                "snowflake_host",
                self.snowflake_host.replace("_", "-"),
            )

    def model_dump(
        self,
        *,
        exclude_none: bool = True,
    ) -> dict:
        """Convert parameters to a dictionary for client initialization.

        Args:
            exclude_none: Whether to exclude fields with value ``None``.
                Defaults to True.
        """
        extra = {
            "snowflake_username": self.snowflake_username,
            "snowflake_password": (
                self.snowflake_password.get_secret_value() if self.snowflake_password else None
            ),
            "snowflake_account": self.snowflake_account,
            "snowflake_host": self.snowflake_host,
            "snowflake_warehouse": self.snowflake_warehouse,
            "snowflake_database": self.snowflake_database,
            "snowflake_schema": self.snowflake_schema,
            "snowflake_role": self.snowflake_role,
        }

        return super().model_dump(exclude_none=exclude_none, extra=extra)

    def model_copy(self, *, update: dict | None = None) -> "CortexPlatformParameters":
        """Create a new instance of the model with the same values as
        the current instance.

        Args:
            update: A dictionary of values to update in the new instance.

        Returns:
            A new instance of CortexParameters with updated values.
        """
        # Start with current direct parameters
        current_params = {f.name: getattr(self, f.name) for f in fields(self) if f.init}

        if not update:
            current_params = {k: v for k, v in current_params.items() if v is not None}
            return CortexPlatformParameters(**current_params)

        # Merge all parameters
        final_params = {**current_params, **update}
        final_params = {k: v for k, v in final_params.items() if v is not None}
        return CortexPlatformParameters(**final_params)

    @classmethod
    def model_validate(cls, obj: dict) -> "CortexPlatformParameters":
        obj = dict(obj)  # Create a copy to avoid modifying the original

        # Convert datetime strings back to datetime objects
        cls._convert_datetime_fields(obj)

        # Directly pass the dictionary to the constructor.
        # The constructor and __post_init__ will handle extra parameters.
        if "snowflake_password" in obj:
            obj["snowflake_password"] = SecretString(
                obj["snowflake_password"],
            )
        return cls(**obj)


PlatformParameters.register_platform_parameters("cortex", CortexPlatformParameters)
