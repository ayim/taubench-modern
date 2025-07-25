from dataclasses import dataclass, field, fields
from typing import Any, Literal

from agent_platform.core.platforms.base import PlatformParameters


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
        config_params: Used to instantiate a botocore.config.Config object for
        advanced settings. Common options include:
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
            config_params={'connect_timeout': 5, 'read_timeout': 60}
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

    config_params: dict = field(default_factory=dict, repr=False)

    def __post_init__(self):
        # This is just here so, if in the future, we want a post init
        # we don't forget to call super().__post_init__()
        super().__post_init__()

    def aws_client_params(self) -> dict[str, Any]:
        """Return only the parameters needed for AWS client initialization.

        This method filters out base class metadata fields and config_params
        (which is handled separately via AioConfig), returning only the
        AWS-specific client parameters.

        Returns:
            Dictionary of AWS client parameters with None values excluded.
        """
        aws_params = {
            "region_name": self.region_name,
            "api_version": self.api_version,
            "use_ssl": self.use_ssl,
            "verify": self.verify,
            "endpoint_url": self.endpoint_url,
            "aws_access_key_id": self.aws_access_key_id,
            "aws_secret_access_key": self.aws_secret_access_key,
            "aws_session_token": self.aws_session_token,
        }

        # Filter out None values
        return {k: v for k, v in aws_params.items() if v is not None}

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
            "region_name": self.region_name,
            "api_version": self.api_version,
            "use_ssl": self.use_ssl,
            "verify": self.verify,
            "endpoint_url": self.endpoint_url,
            "aws_access_key_id": self.aws_access_key_id,
            "aws_secret_access_key": self.aws_secret_access_key,
            "aws_session_token": self.aws_session_token,
            "config_params": self.config_params,
        }

        return super().model_dump(exclude_none=exclude_none, extra=extra)

    def model_copy(self, *, update: dict | None = None) -> "BedrockPlatformParameters":
        """Create a new instance of the model with the same values as
        the current instance.

        Args:
            update: A dictionary of values to update in the new instance.

        Returns:
            A new instance of BedrockParameters with updated values.
        """
        data = self.model_dump(exclude_none=False)
        data.update(update or {})
        data.pop("kind", None)
        return BedrockPlatformParameters(**data)

    @classmethod
    def model_validate(cls, obj: dict) -> "BedrockPlatformParameters":
        obj = dict(obj)  # don't mutate caller's dict

        # Remove kind, it's force-set to "bedrock"
        if "kind" in obj:
            obj.pop("kind")

        # 1.) Unify the various ways extra params might come in
        legacy = obj.pop("_extra_config_params", None)
        config_params = obj.pop("config_params", None) or {}
        if legacy:
            config_params |= legacy  # legacy wins if key repeats

        # 2.) Lift any stray Config-style keys that are not dataclass fields
        top_fields = {f.name for f in fields(cls)}
        stray = {k: obj.pop(k) for k in list(obj) if k not in top_fields}
        config_params |= stray

        # 3.) Convert datetime strings back to datetime objects
        cls._convert_datetime_fields(obj)

        # 4.) Return the new instance
        obj["config_params"] = config_params
        return cls(**obj)


PlatformParameters.register_platform_parameters("bedrock", BedrockPlatformParameters)
