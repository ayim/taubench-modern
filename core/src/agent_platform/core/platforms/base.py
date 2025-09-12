import uuid
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, ClassVar, Generic, TypeVar

from agent_platform.core.configurations import Configuration
from agent_platform.core.configurations.base import FieldMetadata
from agent_platform.core.delta import GenericDelta
from agent_platform.core.kernel_interfaces.kernel_mixin import UsesKernelMixin
from agent_platform.core.prompts import Prompt
from agent_platform.core.prompts.base import PromptMessage
from agent_platform.core.prompts.content import (
    PromptAudioContent,
    PromptDocumentContent,
    PromptImageContent,
    PromptMessageContent,
    PromptTextContent,
    PromptToolResultContent,
    PromptToolUseContent,
)
from agent_platform.core.responses.response import ResponseMessage

if TYPE_CHECKING:
    from agent_platform.core.kernel import Kernel


@dataclass(frozen=True)
class PlatformPrompt(ABC):
    """A platform-specific prompt that can be converted to a platform-specific request
    via the `as_platform_request` method.
    """

    @abstractmethod
    def as_platform_request(self, model: str, stream: bool = False) -> Any:
        """Convert the prompt to a platform-specific request.

        Args:
            model: The platform-specific model ID to use to generate the request.
            stream: Whether to generate a stream request.

        Returns:
            A platform-specific request.
        """
        pass


@dataclass(frozen=True, kw_only=True)
class PlatformParameters(ABC):
    """A platform-specific parameters."""

    _platform_parameters_registry: ClassVar[dict[str, type["PlatformParameters"]]] = {}

    kind: str = field(
        default="platform",
        metadata={"description": "The kind of platform parameters."},
        init=False,
    )
    """The kind of platform parameters."""

    name: str = field(
        default="",
        metadata={"description": "The name of the platform parameters."},
    )
    """The name of the platform parameters."""

    description: str | None = field(
        default=None,
        metadata={"description": "The description of the platform parameters."},
    )
    """The description of the platform parameters."""

    models: dict[str, list[str]] | None = field(
        default=None,
        metadata={
            "description": (
                "Allow list of provider -> models mapping (e.g. {'openai': ['gpt-4-1', 'o3']})"
            ),
        },
    )
    """Allow list of provider -> models mapping (e.g. {'openai': ['gpt-4-1', 'o3']})

    If not provided, or empty, the platform will default to the
    allowlist to constrain model selection to what agent-server _used to pick_
    prior to the introduction of this field. (This is to prevent breaking
    changes for existing agents.)
    """

    created_at: datetime = field(
        default_factory=lambda: datetime.now(UTC),
        metadata={"description": "The time at which the platform parameters were created."},
    )
    """The time at which the platform parameters were created."""

    updated_at: datetime = field(
        default_factory=lambda: datetime.now(UTC),
        metadata={"description": "The time at which the platform parameters were last updated."},
    )
    """The time at which the platform parameters were last updated."""

    platform_id: str = field(
        default_factory=lambda: str(uuid.uuid4()),
        metadata={"description": "The unique identifier of the platform."},
    )
    """The unique identifier of the platform."""

    def __post_init__(self) -> None:
        """Ensures the `name` field is non-empty and converts string datetime fields to
        `datetime` objects if necessary.

        Specifically, if the `created_at` or `updated_at` fields are provided as strings
        (rather than `datetime` objects), this method attempts to parse them using
        `datetime.fromisoformat`.

        The expected string format is ISO 8601, e.g., '2023-01-15T10:30:00+00:00'.

        Raises a `ValueError` if the string cannot be parsed as an ISO 8601 datetime."""
        if not self.name:
            object.__setattr__(self, "name", f"{self.kind}-parameters")

        # Convert string datetime fields to datetime objects if needed
        # This provides a safety net in case string datetimes slip
        # through model_validate
        for field_name in ["created_at", "updated_at"]:
            field_value = getattr(self, field_name)
            if isinstance(field_value, str):
                try:
                    converted_value = datetime.fromisoformat(field_value)
                    object.__setattr__(self, field_name, converted_value)
                except ValueError as e:
                    raise ValueError(
                        f"Invalid datetime string for {field_name}: {field_value!r}. "
                        f"Expected ISO format (e.g., '2023-01-15T10:30:00+00:00')"
                    ) from e

    @abstractmethod
    def model_dump(
        self,
        *,
        exclude_none: bool = True,
        extra: dict[str, Any] | None = None,
    ) -> dict:
        """Convert parameters to a dictionary for client initialization.

        Args:
            exclude_none: Whether to exclude fields with value ``None``.
                Defaults to True.
        """
        result = {
            "kind": self.kind,
            "name": self.name,
            "description": self.description,
            "models": self.models,
            "created_at": (
                self.created_at.isoformat()
                if self.created_at and hasattr(self.created_at, "isoformat")
                else self.created_at
            ),
            "updated_at": (
                self.updated_at.isoformat()
                if self.updated_at and hasattr(self.updated_at, "isoformat")
                else self.updated_at
            ),
            "platform_id": self.platform_id,
            **(extra or {}),
        }

        if exclude_none:
            result = {k: v for k, v in result.items() if v is not None}

        return result

    @classmethod
    def register_platform_parameters(
        cls,
        name: str,
        platform_parameters: type["PlatformParameters"],
    ) -> None:
        """Register a platform parameters."""
        cls._platform_parameters_registry[name] = platform_parameters

    @classmethod
    def model_validate(cls, obj: dict) -> "PlatformParameters":
        """Create a platform parameters from a dictionary.

        Args:
            obj: The dictionary to create the platform parameters from.

        Returns:
            The platform parameters.
        """
        obj = dict(obj)  # Create a copy to avoid modifying the original
        kind = obj.pop("kind")
        if kind not in cls._platform_parameters_registry:
            raise ValueError(f"Invalid platform parameters kind: {kind}")

        # Convert datetime strings back to datetime objects
        cls._convert_datetime_fields(obj)

        return cls._platform_parameters_registry[kind].model_validate(obj)

    @classmethod
    def _convert_datetime_fields(cls, obj: dict) -> None:
        """Convert datetime string fields back to datetime objects in-place.

        This helper method should be called by all subclass model_validate
        implementations to ensure consistent datetime handling.

        Args:
            obj: The dictionary to process (modified in-place).
        """
        for datetime_field in ["created_at", "updated_at"]:
            if datetime_field in obj and isinstance(obj[datetime_field], str):
                obj[datetime_field] = datetime.fromisoformat(obj[datetime_field])


class PlatformConverters(ABC, UsesKernelMixin):
    """Platform-specific converters for content kinds to transform agent-server
    prompt types to platform-specific types."""

    # The return types from all these are platform-specific, so how do I express that
    # in the abstract class?

    @abstractmethod
    async def convert_text_content(
        self,
        content: PromptTextContent,
    ) -> Any:
        """Converts a text content to a platform-specific text content."""
        pass

    @abstractmethod
    async def convert_image_content(
        self,
        content: PromptImageContent,
    ) -> Any:
        """Converts an image content to a platform-specific image content."""
        pass

    @abstractmethod
    async def convert_audio_content(
        self,
        content: PromptAudioContent,
    ) -> Any:
        """Converts an audio content to a platform-specific audio content."""
        pass

    @abstractmethod
    async def convert_tool_use_content(
        self,
        content: PromptToolUseContent,
    ) -> Any:
        """Converts a tool use content to a platform-specific tool use content."""
        pass

    @abstractmethod
    async def convert_tool_result_content(
        self,
        content: PromptToolResultContent,
    ) -> Any:
        """Converts a tool result content to a platform-specific tool result content."""
        pass

    @abstractmethod
    async def convert_document_content(
        self,
        content: PromptDocumentContent,
    ) -> Any:
        """Converts a document content to a platform-specific document content."""
        pass

    async def convert_content_item_to_platform_part(
        self,
        content: PromptMessageContent,
    ) -> Any:
        """Converts a content item to a platform-specific content item.

        Raises ValueError if unrecognized content.type.
        """
        ctype = content.kind
        if ctype == "text" and isinstance(content, PromptTextContent):
            return await self.convert_text_content(content)
        elif ctype == "image" and isinstance(content, PromptImageContent):
            return await self.convert_image_content(content)
        elif ctype == "audio" and isinstance(content, PromptAudioContent):
            return await self.convert_audio_content(content)
        elif ctype == "tool_use" and isinstance(content, PromptToolUseContent):
            return await self.convert_tool_use_content(content)
        elif ctype == "tool_result" and isinstance(content, PromptToolResultContent):
            return await self.convert_tool_result_content(content)
        else:
            raise ValueError(f"Unsupported PromptMessageContent type: {ctype}.")

    async def convert_prompt_message_to_platform_message(
        self,
        message: PromptMessage,
    ) -> Any:
        """Converts a prompt message to a platform message."""
        parts = []
        for content in message.content:
            parts.append(await self.convert_content_item_to_platform_part(content))
        return parts

    async def convert_prompt_messages_to_platform_messages(
        self,
        messages: list[PromptMessage],
    ) -> list[Any]:
        """Converts a list of prompt messages to a list of platform messages.

        This is a generic implementation that converts each content item in the
        message to a platform-specific content item. Override this method in a
        subclass to provide a platform-specific implementation.
        """
        parts = []
        for msg in messages:
            # TODO: had to edit here, types are wonky, was this in use?
            parts.append(await self.convert_prompt_message_to_platform_message(msg))
        return parts

    @abstractmethod
    async def convert_prompt(
        self,
        prompt: Prompt,
        model_id: str | None = None,
    ) -> PlatformPrompt:
        """Converts a prompt to a platform-specific prompt.

        Sometimes, there may be model-specific changes for certain
        providers, so we allow a model_id to be provided.
        """
        pass


class PlatformParsers(ABC):
    """Platform-specific parsers for content kinds to transform platform-specific
    types to agent-server response types."""

    # As we are adding more platform clients, it's becoming more clear that
    # it's a bit hard to pin down the exact interface for platform-specific
    # output parsing. Let's revisit this once platforms are more mature.

    @abstractmethod
    def parse_response(self, response: Any) -> ResponseMessage:
        """Parses a platform-specific response to an agent-server model response."""
        pass


class PlatformModelMap(Configuration):
    """A set of mappings between platform model names and agent server model names.

    All mappings keys should be the model name used in the Agent Server.

    This configuration includes various types of mappings to allow for
    selection of models based on type, modality, etc.
    """

    _abstract = True

    model_aliases: dict[str, str] = field(
        default_factory=dict,
        metadata=FieldMetadata(
            description=("A mapping between platform model names and agent server model names."),
        ),
    )
    models_to_type: dict[str, str] = field(
        default_factory=dict,
        metadata=FieldMetadata(
            description=("A mapping between agent server model names and model types."),
        ),
    )
    models_to_input_modalities: dict[str, list[str]] = field(
        default_factory=dict,
        metadata=FieldMetadata(
            description=(
                "A mapping between agent server model names and input modalities "
                "supported by the model."
            ),
        ),
    )
    models_to_output_modalities: dict[str, list[str]] = field(
        default_factory=dict,
        metadata=FieldMetadata(
            description=(
                "A mapping between agent server model names and output modalities "
                "supported by the model."
            ),
        ),
    )
    model_families: dict[str, str] = field(
        default_factory=dict,
        metadata=FieldMetadata(
            description="The model families by model type.",
        ),
    )
    """The model families by model type."""
    model_context_windows: dict[str, int | None] = field(
        default_factory=dict,
        metadata=FieldMetadata(
            description="The maximum context window in tokens for each model.",
        ),
    )
    """The maximum context window in tokens for each model."""

    @classmethod
    def supported_models(cls) -> list[str]:
        """Get list of supported model names."""
        return list(cls.model_aliases.keys())

    @classmethod
    def distinct_llm_model_ids(cls) -> list[str]:
        """Get list of distinct Large Language Model names."""
        return list(
            set(
                model for model in cls.supported_models() if cls.models_to_type.get(model) == "llm"
            ),
        )

    @classmethod
    def llm_models_with_input_modalities(cls, modalities: list[str]) -> list[str]:
        """Get list of model names that support the given input modalities."""
        return [
            model
            for model in cls.distinct_llm_model_ids()
            if all(
                modality in cls.models_to_input_modalities.get(model, []) for modality in modalities
            )
        ]

    @classmethod
    def distinct_llm_model_ids_with_tool_input(cls) -> list[str]:
        """Get list of distinct LLM model IDs that support tool calling."""
        return cls.llm_models_with_input_modalities(["tools"])

    @classmethod
    def distinct_llm_model_ids_with_audio_input(cls) -> list[str]:
        """Get list of distinct LLM model IDs that support audio input."""
        return cls.llm_models_with_input_modalities(["audio"])

    @classmethod
    def distinct_embedding_model_ids(cls) -> list[str]:
        """Get list of distinct embedding model IDs."""
        return list(
            set(
                model
                for model in cls.supported_models()
                if cls.models_to_type[model] == "embedding"
            ),
        )


class PlatformConfigs(Configuration):
    """A platform-specific configs."""

    _abstract = True

    default_platform_provider: dict[str, str] = field(
        default_factory=dict,
        metadata=FieldMetadata(
            description="The default platform provider by model type.",
        ),
    )
    """The default platform provider by model type."""

    default_model_type: str = field(
        default="llm",
        metadata=FieldMetadata(
            description="The default model type.",
        ),
    )
    """The default model type."""

    default_quality_tier: dict[str, str] = field(
        default_factory=dict,
        metadata=FieldMetadata(
            description="The default quality tier by model type.",
        ),
    )
    """The default quality tier by model type."""

    supported_models_by_provider: dict[str, list[str]] = field(
        default_factory=dict,
        metadata=FieldMetadata(
            description="The supported models by provider.",
        ),
    )
    """The supported models by provider."""


# Define type variables for the components
TConverters = TypeVar("TConverters", bound=PlatformConverters)
TParsers = TypeVar("TParsers", bound=PlatformParsers)
TParameters = TypeVar("TParameters", bound=PlatformParameters)
TPrompt = TypeVar("TPrompt", bound=PlatformPrompt)


class PlatformClient(
    ABC,
    UsesKernelMixin,
    Generic[TConverters, TParsers, TParameters, TPrompt],
):
    """Provides a client to interact with a AI platform."""

    NAME: ClassVar[str] = ""
    configs: ClassVar[type[PlatformConfigs]] = PlatformConfigs
    model_map: ClassVar[type[PlatformModelMap]] = PlatformModelMap

    def __init__(
        self,
        *,
        kernel: "Kernel | None" = None,
        parameters: TParameters | None = None,
        **kwargs: Any,
    ):
        """Initialize the platform client.

        Args:
            kernel: The Agent Serverkernel to use for the client.
            parameters: The platform-specific parameters. If not provided, the
                parameters will be initialized using the `_init_parameters` method
                with the provided keyword arguments.
            **kwargs: Additional keyword arguments will be passed to the parameters
                constructor, these will override any values provided in the
                `parameters` argument.
        """
        self._parameters: TParameters = self._init_parameters(parameters, **kwargs)
        self._converters: TConverters = self._init_converters(kernel)
        self._parsers: TParsers = self._init_parsers()

    def attach_kernel(self, kernel: "Kernel") -> None:
        """Attach the kernel to the client."""
        super().attach_kernel(kernel)
        self._converters.attach_kernel(kernel)

    @property
    def name(self) -> str:
        """The name of the platform."""
        return self.NAME

    @property
    def converters(self) -> TConverters:
        """The platform-specific converters."""
        return self._converters

    @property
    def parsers(self) -> TParsers:
        """The platform-specific parsers."""
        return self._parsers

    @property
    def parameters(self) -> TParameters:
        """The platform-specific parameters."""
        return self._parameters

    @abstractmethod
    def _init_converters(self, kernel: "Kernel | None" = None) -> TConverters:
        """Initializes the platform-specific converters."""
        pass

    @abstractmethod
    def _init_parameters(
        self,
        parameters: TParameters | None = None,
        **kwargs: Any,
    ) -> TParameters:
        """Initializes the platform-specific parameters.

        Args:
            defaults: If provided, these values will be used as defaults that can be
                overridden by kwargs.
            **kwargs: Additional keyword arguments will be passed to the parameters
                constructor.
        """
        pass

    @abstractmethod
    def _init_parsers(self) -> TParsers:
        """Initializes the platform-specific parsers."""
        pass

    @abstractmethod
    async def generate_response(
        self,
        prompt: TPrompt,
        model: str,
    ) -> ResponseMessage:
        """Generate a response from the platform.

        Args:
            prompt: The prompt to send to the model.
            model: The model to use for generation.
            ctx: Optional context for telemetry.

        Returns:
            The model's response.
        """
        pass

    @abstractmethod
    def generate_stream_response(
        self,
        prompt: TPrompt,
        model: str,
    ) -> AsyncGenerator[GenericDelta, None]:
        """Generate a streaming response from the platform.

        Args:
            prompt: The prompt to send to the model.
            model: The model to use for generation.
            ctx: Optional context for telemetry.

        Yields:
            GenericDelta objects that update the response.
        """
        pass

    def _generate_platform_metadata(self) -> dict[str, Any]:
        """Generate platform metadata from the response.

        Args:
            response: The response from the platform.
        """
        return {
            "sema4ai_metadata": {
                "platform_name": self.NAME,
            },
        }

    @abstractmethod
    async def create_embeddings(
        self,
        texts: list[str],
        model: str,
    ) -> dict[str, Any]:
        """Create embeddings using a model on the platform.

        Args:
            texts: The texts to create embeddings for.
            model: The model to use to create embeddings.
            ctx: Optional context for telemetry.

        Returns:
            A dictionary containing the embeddings and any additional
            model-specific information.
        """
        pass

    async def get_available_models(self) -> dict[str, list[str]]:
        """Get a map from providers to a list of their models for the platform."""
        return {}

    # Machinery to support a `from_platform_config` classmethod
    _platform_clients: ClassVar[dict[str, type["PlatformClient"]]] = {}

    @classmethod
    def register_platform_client(
        cls,
        name: str,
        platform_client: type["PlatformClient"],
    ) -> None:
        """Register a platform client."""
        cls._platform_clients[name] = platform_client

    @classmethod
    def from_platform_config(
        cls,
        kernel: "Kernel",
        config: PlatformParameters,
        **kwargs: Any,
    ) -> "PlatformClient":
        """Create a platform client from a platform config."""
        # First, find a matching platform client
        for name, platform_client in cls._platform_clients.items():
            if name == config.kind:
                return platform_client(kernel=kernel, parameters=config, **kwargs)
        raise ValueError(f"No platform client found for {config.kind}.")
