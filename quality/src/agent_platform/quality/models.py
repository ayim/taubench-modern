import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from agent_platform.core.utils import SecretString


@dataclass(frozen=True)
class Platform:
    """A platform for testing."""

    name: str

    def as_platform_config(self) -> dict:
        """Convert the platform to a platform config."""
        match self.name:
            case "openai":
                from agent_platform.core.platforms.openai import OpenAIPlatformParameters

                return OpenAIPlatformParameters(
                    openai_api_key=SecretString(os.environ["OPENAI_API_KEY"]),
                ).model_dump()
            case "azure":
                from agent_platform.core.platforms.azure import AzureOpenAIPlatformParameters

                return AzureOpenAIPlatformParameters(
                    azure_api_key=SecretString(os.environ["AZURE_API_KEY"]),
                    azure_endpoint_url=os.environ["AZURE_ENDPOINT_URL"],
                    azure_deployment_name=os.environ["AZURE_DEPLOYMENT_NAME"],
                    azure_deployment_name_embeddings=os.environ["AZURE_DEPLOYMENT_NAME_EMBEDDINGS"],
                    azure_api_version=os.environ["AZURE_API_VERSION"],
                ).model_dump()
            case "bedrock":
                from agent_platform.core.platforms.bedrock import BedrockPlatformParameters

                return BedrockPlatformParameters(
                    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
                    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
                    region_name=os.environ["AWS_DEFAULT_REGION"],
                ).model_dump()
            case "cortex":
                from agent_platform.core.platforms.cortex import CortexPlatformParameters

                return CortexPlatformParameters().model_dump()
            case "groq":
                from agent_platform.core.platforms.groq import GroqPlatformParameters

                return GroqPlatformParameters(
                    groq_api_key=SecretString(os.environ["GROQ_API_KEY"]),
                ).model_dump()
            case "google":
                from agent_platform.core.platforms.google import GooglePlatformParameters

                return GooglePlatformParameters(
                    google_api_key=SecretString(os.environ["GOOGLE_API_KEY"]),
                ).model_dump()
            case "reducto":
                raise NotImplementedError("Reducto is not supported for quality testing")
            case _:
                raise ValueError(f"Unknown platform: {self.name}")


@dataclass
class Thought:
    """A thought from an agent."""

    content: str


@dataclass
class Text:
    """A text message from an agent or user."""

    content: str


@dataclass
class ToolUse:
    """A tool use from an agent."""

    input_as_string: str
    output_as_string: str
    tool_name: str
    started_at: str
    ended_at: str
    error: str | None = None


@dataclass
class Message:
    """A message in a conversation thread."""

    role: Literal["user", "agent"]
    content: list[Thought | Text | ToolUse]


@dataclass
class Thread:
    """A conversation thread for testing."""

    name: str
    description: str
    messages: list[Message]


@dataclass
class Evaluation:
    """An evaluation to run on a completed thread."""

    kind: str
    expected: Any
    description: str


@dataclass
class SFAuthorizationOverride:
    """Overrides for ~/.sema4ai/sf-auth.json."""

    account: str
    role: str
    private_key_path: str
    private_key_passphrase: str
    user: str

    def __post_init__(self):
        """Replace any value that is $ENV_VAR with the actual value of the environment variable."""
        for key, value in self.__dict__.items():
            if isinstance(value, str) and value.startswith("$"):
                env_var_name = value[1:]
                env_value = os.getenv(env_var_name)
                if env_value is None:
                    raise ValueError(
                        f"Environment variable '{env_var_name}' not set, "
                        f"required for sf-auth-override: '{key}'"
                    )
                self.__dict__[key] = env_value


@dataclass
class ActionSecret:
    """A secret for an action."""

    name: str
    value: str


@dataclass
class ActionSecrets:
    """Secrets for an action."""

    name: str
    secrets: list[ActionSecret]


@dataclass
class ActionPackageSecret:
    """Secrets for various actions in an action package."""

    name: str
    actions: list[ActionSecrets]


@dataclass
class TestCase:
    """A complete test case with thread and evaluations."""

    thread: Thread
    target_platforms: list[Platform]
    evaluations: list[Evaluation]
    file_path: Path
    action_secrets: list[ActionPackageSecret]
    sf_auth_override: SFAuthorizationOverride | None = None

    @classmethod
    def from_file(cls, file_path: Path) -> "TestCase":
        """Load a test case from a YAML file."""
        import yaml

        with open(file_path) as f:
            data = yaml.safe_load(f)

        # Parse thread
        thread_data = data["thread"][0]  # Assuming single thread per file
        thread = Thread(
            name=thread_data["name"],
            description=thread_data.get("description", ""),  # Use .get() with default
            messages=[
                Message(
                    role=msg["role"],
                    content=[Text(content=msg["content"])]
                    if isinstance(msg["content"], str)
                    else msg["content"],
                )
                for msg in thread_data["messages"]
            ],
        )

        # Parse target platforms, if none are present we'll default to just
        # openai
        target_platforms = [
            Platform(name=platform["name"])
            for platform in data.get(
                "target-platforms",  # Use hyphen to match YAML format
                [{"name": "openai"}],  # Default to openai if none are present
            )
        ]

        # Parse evaluations
        evaluations = [
            Evaluation(
                kind=eval_data["kind"],
                expected=eval_data["expected"],
                description=eval_data.get("description", ""),  # Use .get() with default
            )
            for eval_data in data.get("evaluations", [])
        ]

        # Parse sf-auth-override if present
        sf_auth_override_data = data.get("sf-auth-override", None)
        if sf_auth_override_data:
            # It must have all the fields
            required_fields = [
                "account",
                "role",
                "private_key_path",
                "private_key_passphrase",
                "user",
            ]
            if not all(field in sf_auth_override_data for field in required_fields):
                raise ValueError(
                    f"sf-auth-override missing one or more required fields: {required_fields}",
                )

        sf_auth_override = (
            SFAuthorizationOverride(
                account=sf_auth_override_data.get("account"),
                role=sf_auth_override_data.get("role"),
                private_key_path=sf_auth_override_data.get("private_key_path"),
                private_key_passphrase=sf_auth_override_data.get("private_key_passphrase"),
                user=sf_auth_override_data.get("user"),
            )
            if sf_auth_override_data
            else None
        )

        # Parse action-secrets
        action_secrets = [
            ActionPackageSecret(
                name=action_package_secret["name"],
                actions=[
                    ActionSecrets(
                        name=action_secret["name"],
                        secrets=[
                            ActionSecret(
                                name=secret["name"],
                                value=secret["value"],
                            )
                            for secret in action_secret["secrets"]
                        ],
                    )
                    for action_secret in action_package_secret["actions"]
                ],
            )
            for action_package_secret in data.get("action-secrets", [])
        ]

        return cls(
            thread=thread,
            target_platforms=target_platforms,
            evaluations=evaluations,
            file_path=file_path,
            action_secrets=action_secrets,
            sf_auth_override=sf_auth_override,
        )


@dataclass
class AgentPackage:
    """An agent package for testing."""

    name: str
    path: Path
    zip_path: Path


@dataclass
class TestResult:
    """Result of running a test evaluation."""

    evaluation: Evaluation
    passed: bool
    actual_value: Any
    error: str | None = None


@dataclass
class ThreadResult:
    """Result of running a complete thread test."""

    test_case: TestCase
    platform: Platform
    agent_messages: list[Message]
    evaluation_results: list[TestResult]
    success: bool
    error: str | None = None
