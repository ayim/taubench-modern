from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

from agent_platform.core.configurations import Configuration
from agent_platform.core.delta import GenericDelta
from agent_platform.core.kernel_interfaces.kernel_mixin import UsesKernelMixin
from agent_platform.core.model_selector import ModelSelector
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
from agent_platform.core.responses.content import (
    ResponseAudioContent,
    ResponseDocumentContent,
    ResponseImageContent,
    ResponseMessageContent,
    ResponseTextContent,
    ResponseToolUseContent,
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


@dataclass(frozen=True)
class PlatformParameters(ABC):
    """A platform-specific parameters."""

    _platform_parameters_registry: ClassVar[
        dict[str, type["PlatformParameters"]]
    ] = {}

    kind: str = field(
        default="platform",
        metadata={"description": "The kind of platform parameters."},
        init=False,
    )
    """The kind of platform parameters."""

    @abstractmethod
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
            exclude_unset: Whether to exclude fields that were not
                explicitly set. Not implemented.
            exclude_defaults: Whether to exclude fields that are set to their
                default values. Not implemented.
        """
        pass

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
        kind = obj.pop("kind")
        if kind not in cls._platform_parameters_registry:
            raise ValueError(f"Invalid platform parameters kind: {kind}")
        return cls._platform_parameters_registry[kind].model_validate(obj)


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
        if ctype == "text":
            return await self.convert_text_content(content)
        elif ctype == "image":
            return await self.convert_image_content(content)
        elif ctype == "audio":
            return await self.convert_audio_content(content)
        elif ctype == "tool_use":
            return await self.convert_tool_use_content(content)
        elif ctype == "tool_result":
            return await self.convert_tool_result_content(content)
        else:
            raise ValueError(f"Unsupported PromptMessageContent type: {ctype}.")

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
            parts.append(await self.convert_content_item_to_platform_part(msg))
        return parts

    @abstractmethod
    async def convert_prompt(self, prompt: Prompt) -> PlatformPrompt:
        """Converts a prompt to a platform-specific prompt."""
        pass


class PlatformParsers(ABC):
    """Platform-specific parsers for content kinds to transform platform-specific
    types to agent-server response types."""

    # For Bedrock at least, all streamed content is str which may ultimately be
    # bytes or a serialized JSON object, but a sync response may have more
    # specific types (e.g., an image will have a `bytes` object).

    @abstractmethod
    def parse_text_content(self, content: str | bytes | dict) -> ResponseTextContent:
        """Parses a platform-specific text content to an agent-server text content."""
        pass

    @abstractmethod
    def parse_image_content(self, content: str | bytes | dict) -> ResponseImageContent:
        """Parses a platform-specific image content to an agent-server image content."""
        pass

    @abstractmethod
    def parse_audio_content(self, content: str | bytes | dict) -> ResponseAudioContent:
        """Parses a platform-specific audio content to an agent-server audio content."""
        pass

    @abstractmethod
    def parse_tool_use_content(
        self,
        content: str | bytes | dict,
    ) -> ResponseToolUseContent:
        """Parses a platform-specific tool use content to an agent-server
        tool use content."""

    @abstractmethod
    def parse_document_content(
        self,
        content: str | bytes | dict,
    ) -> ResponseDocumentContent:
        """Parses a platform-specific document content to an agent-server
        document content."""
        pass

    @abstractmethod
    def parse_content_item(self, item: str | bytes | dict) -> ResponseMessageContent:
        """Parses a platform-specific content item to an agent-server content item."""
        pass

    @abstractmethod
    def parse_response(self, response: str | bytes | dict) -> ResponseMessage:
        """Parses a platform-specific response to an agent-server model response."""
        pass


@dataclass(frozen=True)
class PlatformConfigs(Configuration):
    """A platform-specific configs."""

    default_platform_provider: dict[str, str] = field(
        default_factory=lambda: {
            "llm": "openai",
            "embedding": "openai",
            "text-to-image": "openai",
        },
        metadata={
            "description": "The default platform provider by model type.",
        },
    )
    """The default platform provider by model type."""

    default_model_type: str = field(
        default="llm",
        metadata={"description": "The default model type."},
    )
    """The default model type."""

    default_quality_tier: dict[str, str] = field(
        default_factory=lambda: {
            "llm": "balanced",
            "embedding": "balanced",
            "text-to-image": "balanced",
        },
        metadata={
            "description": "The default quality tier by model type.",
        },
    )
    """The default quality tier by model type."""

    supported_models_by_provider: dict[str, list[str]] = field(
        default_factory=dict,
        metadata={"description": "The supported models by provider."},
    )
    """The supported models by provider."""


class PlatformClient(ABC, UsesKernelMixin):
    """Provides a client to interact with a AI platform."""

    NAME: ClassVar[str] = ""

    def __init__(
        self,
        *,
        kernel: "Kernel | None" = None,
        parameters: PlatformParameters | dict | None = None,
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
        self._parameters = self._init_parameters(parameters, **kwargs)
        self._converters = self._init_converters(kernel)
        self._parsers = self._init_parsers()
        self._configs = self._init_configs()

    def attach_kernel(self, kernel: "Kernel") -> None:
        """Attach the kernel to the client."""
        super().attach_kernel(kernel)
        self._converters.attach_kernel(kernel)

    @property
    def name(self) -> str:
        """The name of the platform."""
        return self.NAME

    @property
    def converters(self) -> PlatformConverters:
        """The platform-specific converters."""
        return self._converters

    @property
    def parsers(self) -> PlatformParsers:
        """The platform-specific parsers."""
        return self._parsers

    @property
    def parameters(self) -> PlatformParameters:
        """The platform-specific parameters."""
        return self._parameters

    @property
    def configs(self) -> PlatformConfigs:
        """The platform-specific configs."""
        return self._configs

    @abstractmethod
    def _init_converters(self, kernel: "Kernel | None" = None) -> PlatformConverters:
        """Initializes the platform-specific converters."""
        pass

    @abstractmethod
    def _init_parameters(
        self,
        parameters: PlatformParameters | dict | None = None,
        **kwargs: Any,
    ) -> PlatformParameters:
        """Initializes the platform-specific parameters.

        Args:
            defaults: If provided, these values will be used as defaults that can be
                overridden by kwargs.
            **kwargs: Additional keyword arguments will be passed to the parameters
                constructor.
        """
        pass

    @abstractmethod
    def _init_configs(self) -> PlatformConfigs:
        """Initializes the platform-specific configs."""
        pass

    @abstractmethod
    def _init_parsers(self) -> PlatformParsers:
        """Initializes the platform-specific parsers."""
        pass

    @abstractmethod
    async def generate_response(
        self,
        prompt: PlatformPrompt,
        model: ModelSelector,
    ) -> ResponseMessage:
        """Generates a response to a prompt.

        Arguments:
            prompt: The prompt to generate a response for.

        Returns:
            The generated model response.
        """
        pass

    @abstractmethod
    async def generate_stream_response(
        self,
        prompt: PlatformPrompt,
        model: ModelSelector,
    ) -> AsyncGenerator[GenericDelta, None]:
        """Streams a response to a prompt.

        Arguments:
            prompt: The prompt to generate a stream of responses for.

        Returns:
            A stream of responses from the model.
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
        model: ModelSelector,
    ) -> dict[str, Any]:
        """Create embeddings using a model on the platform.

        Args:
            texts: The texts to create embeddings for.
            model: The model to use to create embeddings.

        Returns:
            A dictionary containing the embeddings and any additional
            model-specific information.
        """
        pass

    # Machinery to support a `from_platform_config` classmethod
    _platform_clients: ClassVar[dict[str, type["PlatformClient"]]] = {}

    @classmethod
    def register_platform_client(
        cls,
        name: str,
        platform_client: "PlatformClient",
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
