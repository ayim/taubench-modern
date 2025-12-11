from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from agent_platform.core.utils import SecretString

if TYPE_CHECKING:
    from agent_platform.core.files.files import UploadedFile


@dataclass
class SDMConfig:
    """Semantic Data Model configuration for a test."""

    kind: Literal["excel", "postgres"]
    sdm_path: str  # Relative to quality/test-data/
    description: str | None = None


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
                    # TODO: read this from yaml configs, just trying to run on gpt-5 as a kind
                    # of integration test for now, but should be configurable
                    models={"openai": ["gpt-5-2-low"]},
                ).model_dump()
            case "azure":
                from agent_platform.core.platforms.azure import AzureOpenAIPlatformParameters

                return AzureOpenAIPlatformParameters(
                    azure_api_key=SecretString(os.environ["AZURE_API_KEY"]),
                    azure_endpoint_url=os.environ["AZURE_ENDPOINT_URL"],
                    azure_deployment_name=os.environ["AZURE_DEPLOYMENT_NAME"],
                    azure_deployment_name_embeddings=os.environ["AZURE_DEPLOYMENT_NAME_EMBEDDINGS"],
                    azure_api_version=os.environ["AZURE_API_VERSION"],
                    # We should be upgrading the eval harness, now that we have this filtering
                    # ability, to have explicit models set (instead of taking platform defaults)
                    models={"openai": ["o3-high"]},
                ).model_dump()
            case "bedrock":
                from agent_platform.core.platforms.bedrock import BedrockPlatformParameters

                return BedrockPlatformParameters(
                    aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
                    aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
                    region_name=os.environ["AWS_DEFAULT_REGION"],
                    # Force to sonnet 4 thinking medium
                    models={"anthropic": ["claude-4-sonnet-thinking-medium"]},
                ).model_dump()
            case "cortex":
                from agent_platform.core.platforms.cortex import CortexPlatformParameters

                return CortexPlatformParameters().model_dump()
            case "groq":
                from agent_platform.core.platforms.groq import GroqPlatformParameters

                return GroqPlatformParameters(
                    groq_api_key=SecretString(os.environ["GROQ_API_KEY"]),
                    models={"groq": ["openai/gpt-oss-120b"]},
                ).model_dump()
            case "google":
                from agent_platform.core.platforms.google import GooglePlatformParameters
                from agent_platform.core.platforms.google.parameters import (
                    extract_vertex_platform_kwargs_from_env,
                )

                params_kwargs = extract_vertex_platform_kwargs_from_env(["gemini-3-pro-preview"])

                return GooglePlatformParameters(**params_kwargs).model_dump()
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
    tool_call_id: str
    started_at: str
    ended_at: str
    error: str | None = None


@dataclass
class FileAttachment:
    """A file attachment"""

    description: str
    mime_type: str
    file_name: str


@dataclass
class Message:
    """A message in a conversation thread."""

    role: Literal["user", "agent"]
    content: list[Thought | Text | ToolUse | FileAttachment]


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
class OAuthAccessToken:
    """OAuth secret."""

    provider: str
    scopes: list[str]
    access_token: str


@dataclass
class ActionSecret:
    """A secret for an action."""

    name: str
    value: str | OAuthAccessToken


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
class Metric:
    name: str
    k: int


@dataclass
class Workitem:
    messages: list[Message]
    payload: dict
    # indicates if we want to test if the workitem is valid
    is_preview_only: bool


@dataclass
class WorkitemResult:
    status: str


@dataclass
class TestRunResult:
    thread_id: str | None
    agent_messages: list[Message]
    workitem_result: WorkitemResult | None


@dataclass
class TestCase:
    """A complete test case with thread and evaluations."""

    name: str
    description: str
    thread: Thread | None
    workitem: Workitem | None
    target_platforms: list[Platform]
    evaluations: list[Evaluation]
    file_path: Path
    action_secrets: list[ActionPackageSecret]
    sdms: list[SDMConfig] = field(default_factory=list)
    sf_auth_override: SFAuthorizationOverride | None = None
    trials: int = field(default=1)
    metrics: list[Metric] = field(default_factory=list)
    timeout_seconds: float | None = None

    @classmethod
    def from_file(cls, file_path: Path) -> TestCase:  # noqa: C901
        """Load a test case from a YAML file."""
        import yaml

        with open(file_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        def parse_content(content: Any):
            if isinstance(content, str):
                return Text(content=content)

            match content["kind"]:
                case "text":
                    return Text(content=content["text"])
                case "attachment":
                    return FileAttachment(
                        file_name=content["file_name"],
                        description=content["description"],
                        mime_type=content["mime_type"],
                    )
                case "thought":
                    return Thought(content=content["text"])
                case "tool_use":
                    return ToolUse(
                        tool_name=content["tool_name"],
                        tool_call_id=content["tool_call_id"],
                        input_as_string=content["input_as_string"],
                        output_as_string=content["output_as_string"],
                        ended_at=content.get("ended_at"),
                        started_at=content.get("started_at"),
                        error=content.get("error", None),
                    )

            raise ValueError(f"Unknown message content type {content}")

        thread = None
        if len(data.get("thread", [])) > 0:
            thread_data = data["thread"][0]  # Assuming single thread per file
            thread = Thread(
                name=thread_data["name"],
                description=thread_data.get("description", ""),  # Use .get() with default
                messages=[
                    Message(role=msg["role"], content=[parse_content(msg["content"])])
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

        trials = data.get("trials", 1)
        timeout_seconds = data.get("timeout_seconds") or data.get("timeout-seconds")
        metrics = [Metric(**m) for m in data.get("metrics", [])]

        sdms = [
            SDMConfig(
                kind=sdm_config["kind"],
                sdm_path=sdm_config["sdm_path"],
                description=sdm_config.get("description"),
            )
            for sdm_config in data.get("sdms", [])
        ]

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

        workitem = None
        if len(data.get("workitem", [])) > 0:
            workitem_data = data["workitem"][0]  # Assuming single workitem per file
            workitem = Workitem(
                messages=[
                    Message(role=msg["role"], content=[parse_content(msg["content"])])
                    for msg in workitem_data["messages"]
                ],
                payload=workitem_data.get("payload", {}),
                is_preview_only=workitem_data.get("isPreviewOnly", False),
            )

        if thread is not None and workitem is not None:
            raise ValueError("Invalid test file: either thread or workitem should be specified.")

        if thread is None and workitem is None:
            raise ValueError("Invalid test file: missing either thread or workitem.")

        return cls(
            name=data.get("name"),
            description=data.get("description"),
            trials=trials,
            metrics=metrics,
            timeout_seconds=timeout_seconds,
            thread=thread,
            target_platforms=target_platforms,
            evaluations=evaluations,
            file_path=file_path,
            action_secrets=action_secrets,
            sf_auth_override=sf_auth_override,
            workitem=workitem,
            sdms=sdms,
        )


@dataclass
class AgentPackage:
    """An agent package for testing."""

    name: str
    path: Path
    zip_path: Path | None = None  # Optional for preinstalled agents
    is_preinstalled: bool = False  # Flag for preinstalled test agents
    preinstalled_key: str | None = None  # Key for preinstalled agent (e.g., "sql-generation")
    agent_id: str | None = None  # For preinstalled agents, store their ID

    # @TODO (agent-cli sunset):
    # Remove this method and agent-cli dependency, and use "read_agent_package_metadata" from
    # agent_platform.core.agent_package.metadata instead.
    async def extract_package_metadata(self) -> Any:
        """Agent Metadata contain info from yaml/json file but also Python code."""
        if self.is_preinstalled:
            # Preinstalled agents have minimal metadata
            return [
                {
                    "name": self.name,
                    "description": "Preinstalled test agent",
                    "oauth": [],  # No OAuth for internal agents
                    "docker_mcp_gateway": {},
                }
            ]

        import json
        import subprocess

        from agent_platform.orchestrator.default_locations import get_action_server_executable_path

        # agent cli is deprecated and shouldn't be used elsewhere
        # here it is needed to extract oauth variables from python code
        def get_agent_cli_executable_path(version: str, download: bool = False) -> Path:
            from sema4ai.common import tools

            target_location = tools.AgentCliTool.get_default_executable(
                version=version, download=download
            )
            return target_location

        agent_cli_exe = get_agent_cli_executable_path(version="v2.0.6", download=True)

        env = os.environ.copy()
        action_server_executable = get_action_server_executable_path()
        # Set the action-server for the agent-cli.
        env["ACTION_SERVER_BIN_PATH"] = str(action_server_executable)

        if self.zip_path is None:
            raise ValueError(f"Agent package zip not found for {self.name}")

        result = subprocess.run(
            [agent_cli_exe, "package", "metadata", "--package", self.zip_path],
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )

        if result.returncode != 0:
            raise ValueError(f"Cannot extract agent {self.name} metadata: {result.stderr}")

        return json.loads(result.stdout)


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
    agent_id: str | None = None
    thread_id: str | None = None
    error: str | None = None
    thread_files: list[UploadedFile] = field(default_factory=list)


@dataclass
class TestResultGroup:
    thread_results: list[ThreadResult]
