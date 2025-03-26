from dataclasses import dataclass, field, fields
from typing import TYPE_CHECKING, Literal, Self

from agent_server_types_v2.platforms.base import PlatformParameters

if TYPE_CHECKING:
    from botocore.config import Config


@dataclass(frozen=True, kw_only=True)
class BedrockPlatformParameters(PlatformParameters):
    """Parameters for the Bedrock platform.

    This class encapsulates all configuration parameters for AWS Bedrock
    client initialization. It supports both direct client parameters and
    advanced configuration via the botocore Config object.

    Direct Parameters:
        region_name: The AWS region to use (e.g., 'us-west-2', 'us-east-1').
            If not specified, boto3 will use the default region from AWS configuration.
        api_version: The API version to use. Generally should be left as
            None to use the latest.
        use_ssl: Whether to use SSL when communicating with AWS (True by default).
        verify: Whether to verify SSL certificates. Can be True/False or path
            to a CA bundle.
        endpoint_url: Alternative endpoint URL (e.g., for VPC endpoints or testing).
            Format: 'https://bedrock.us-east-1.amazonaws.com'
        aws_access_key_id: AWS access key. If not provided, boto3 will use the
            AWS configuration chain (environment, credentials file, IAM role).
        aws_secret_access_key: AWS secret key. Required if aws_access_key_id
            is provided.
        aws_session_token: Temporary session token for STS credentials.

    Advanced Configuration:
        config: A botocore.config.Config object for advanced settings. Common
        options include:
            - retries: Dict controlling retry behavior (e.g., {'max_attempts': 3})
            - connect_timeout: Connection timeout in seconds
            - read_timeout: Read timeout in seconds
            - max_pool_connections: Max connections to keep in connection pool
            - proxies: Dict of proxy servers to use
            - proxies_config: Proxy configuration including CA bundles
            - user_agent: Custom user agent string
            - user_agent_extra: Additional user agent string
            - tcp_keepalive: Whether to use TCP keepalive
            - client_cert: Path to client-side certificate for TLS auth
            - inject_host_prefix: Whether to inject host prefix into endpoint

    Examples:
        Basic usage with region:
        ```python
        params = BedrockPlatformParameters(region_name='us-east-1')
        ```

        Using custom endpoint and credentials:
        ```python
        params = BedrockPlatformParameters(
            endpoint_url='https://bedrock.custom.endpoint',
            aws_access_key_id='YOUR_KEY',
            aws_secret_access_key='YOUR_SECRET'
        )
        ```

        Advanced configuration with retries and timeouts:
        ```python
        params = BedrockPlatformParameters(
            region_name='us-east-1',
            retries={'max_attempts': 3},
            connect_timeout=5,
            read_timeout=60
        )
        ```
    """

    kind: Literal["bedrock"] = field(
        default="bedrock",
        metadata={"description": "The kind of platform parameters."},
        init=False,
    )
    """The kind of platform parameters."""

    # Direct client parameters
    region_name: str | None = field(
        default=None,
        metadata={
            "description": "AWS region name (e.g., 'us-west-2'). If not specified, "
            "boto3 will use the default region from AWS configuration chain "
            "(environment variables, config file, or instance metadata).",
            "example": "us-east-1",
        },
    )

    api_version: str | None = field(
        default=None,
        metadata={
            "description": "API version to use for the AWS service. Generally should "
            "be left as None to use the latest available version. Only set this if "
            "you need a specific API version for compatibility.",
            "example": "2023-04-20",
        },
    )

    use_ssl: bool | None = field(
        default=None,
        metadata={
            "description": "Whether to use SSL/TLS when communicating with AWS "
            "(True by default). Setting this to False is not recommended in "
            "production environments.",
            "example": True,
        },
    )

    verify: bool | str | None = field(
        default=None,
        metadata={
            "description": "Controls SSL certificate verification. Can be:\n"
            "- True: Verify certificates using system CA store (default)\n"
            "- False: Disable verification (not recommended)\n"
            "- str: Path to custom CA bundle file",
            "example": "/path/to/custom/ca-bundle.pem",
        },
    )

    endpoint_url: str | None = field(
        default=None,
        metadata={
            "description": "Alternative endpoint URL for the AWS service. Useful for:\n"
            "- VPC endpoints\n"
            "- Testing with local endpoints\n"
            "- Custom service endpoints\n"
            "Format should be a complete URL including scheme (https://)",
            "example": "https://bedrock.us-east-1.amazonaws.com",
        },
    )

    aws_access_key_id: str | None = field(
        default=None,
        metadata={
            "description": "AWS access key ID for authentication. If not provided, "
            "boto3 will attempt to find credentials in the following order:\n"
            "1. Environment variables\n"
            "2. Shared credential file (~/.aws/credentials)\n"
            "3. IAM role for EC2 instance or ECS task",
            "example": "AKIAIOSFODNN7EXAMPLE",
        },
    )

    aws_secret_access_key: str | None = field(
        default=None,
        metadata={
            "description": "AWS secret access key for authentication. Required if "
            "aws_access_key_id is provided. Should be kept secure and not exposed in "
            "code or logs.",
            "example": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        },
    )

    aws_session_token: str | None = field(
        default=None,
        metadata={
            "description": "Temporary session token for AWS STS (Security Token "
            "Service) credentials. Only required when using temporary credentials "
            "(e.g., from AssumeRole or federated access).",
            "example": "AQoEXAMPLEH4aoAH0gNCAPyJxz4BlCFFxWNE1OPTgk5TthT+...",
        },
    )

    _extra_config_params: dict | None = field(default=None, init=False, repr=False)

    @property
    def config(self) -> "Config | None":
        """The botocore Config object for advanced client configuration."""
        return self._config

    def __post_init__(self) -> None:
        """Process any extra kwargs as Config parameters after dataclass
        initialization."""
        object.__setattr__(self, "_config", None)

        # Get all dataclass fields that are meant for initialization
        all_fields = {f.name for f in fields(self) if f.init}

        # Get any parameters that aren't part of our declared fields
        extra_params = {}
        to_delete = []
        for k, v in vars(self).items():
            if k not in all_fields and not k.startswith("_"):
                extra_params[k] = v
                to_delete.append(k)

        # Pop kind from extra_params if it exists
        extra_params.pop("kind", None)

        # Delete the extra attributes after iteration
        # (Can't do this in the above loop, or you'll get a RuntimeError)
        for k in to_delete:
            object.__delattr__(self, k)

        if extra_params:
            from botocore.config import Config

            # Store for later use in model_copy
            object.__setattr__(self, "_extra_config_params", extra_params)

            # Create or update the Config object
            new_config = Config(**extra_params)
            if self._config is None:
                object.__setattr__(self, "_config", new_config)
            else:
                object.__setattr__(self, "_config", self._config.merge(new_config))

    def model_dump(
        self,
        *,
        exclude_none: bool = True,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
    ) -> dict:
        """Convert parameters to a dictionary for client initialization.

        Args:
            exclude_none: Whether to exclude fields with value ``None``.
                Defaults to True.
            exclude_unset: Whether to exclude fields that were not explicitly set.
                Not implemented.
            exclude_defaults: Whether to exclude fields that are set to their
                default values. Not implemented.
        """
        result = {
            "kind": self.kind,
            "region_name": self.region_name,
            "api_version": self.api_version,
            "use_ssl": self.use_ssl,
            "verify": self.verify,
            "endpoint_url": self.endpoint_url,
            "aws_access_key_id": self.aws_access_key_id,
            "aws_secret_access_key": self.aws_secret_access_key,
            "aws_session_token": self.aws_session_token,
            "config": self._config,
        }

        if exclude_none:
            result = {k: v for k, v in result.items() if v is not None}

        return result

    def model_copy(self, *, update: dict | None = None) -> Self:
        """Create a new instance of the model with the same values as
        the current instance.

        Args:
            update: A dictionary of values to update in the new instance.

        Returns:
            A new instance of BedrockParameters with updated values.
        """
        # Start with current direct parameters
        current_params = {f.name: getattr(self, f.name) for f in fields(self) if f.init}

        # Add stored extra config params if they exist
        if self._extra_config_params:
            current_params.update(self._extra_config_params)

        if not update:
            current_params = {k: v for k, v in current_params.items() if v is not None}
            return BedrockPlatformParameters(**current_params)

        # Split updates into direct params and config params
        direct_param_names = {f.name for f in fields(self) if f.init}
        update_params = {}
        config_updates = {}

        for k, v in update.items():
            if k in direct_param_names:
                update_params[k] = v
            else:
                config_updates[k] = v

        # Merge all parameters
        final_params = {**current_params, **update_params, **config_updates}
        final_params = {k: v for k, v in final_params.items() if v is not None}
        return BedrockPlatformParameters(**final_params)

    @classmethod
    def model_validate(cls, obj: dict) -> "BedrockPlatformParameters":
        # Directly pass the dictionary to the constructor.
        # The constructor and __post_init__ will handle extra parameters.
        return cls(**obj)


PlatformParameters.register_platform_parameters("bedrock", BedrockPlatformParameters)
