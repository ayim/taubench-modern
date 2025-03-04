from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any, ClassVar

from agent_server_types_v2.configurations import Configuration
from agent_server_types_v2.kernel import Kernel
from agent_server_types_v2.kernel_interfaces.kernel_mixin import UsesKernelMixin
from agent_server_types_v2.models.model import Model
from agent_server_types_v2.models.provider import ModelProvider
from agent_server_types_v2.prompts import Prompt
from agent_server_types_v2.prompts.base import PromptMessage
from agent_server_types_v2.prompts.content import (
    PromptAudioContent,
    PromptDocumentContent,
    PromptImageContent,
    PromptMessageContent,
    PromptTextContent,
    PromptToolResultContent,
    PromptToolUseContent,
)
from agent_server_types_v2.responses.content import (
    ResponseAudioContent,
    ResponseDocumentContent,
    ResponseImageContent,
    ResponseMessageContent,
    ResponseTextContent,
    ResponseToolUseContent,
)
from agent_server_types_v2.responses.response import ResponseMessage


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


class PlatformConverters(ABC, UsesKernelMixin):
    """Platform-specific converters for content kinds to transform agent-server
    prompt types to platform-specific types."""

    # The return types from all these are platform-specific, so how do I express that
    # in the abstract class?

    @abstractmethod
    def convert_text_content(self, content: PromptTextContent) -> Any:
        """Converts a text content to a platform-specific text content."""
        pass

    @abstractmethod
    def convert_image_content(self, content: PromptImageContent) -> Any:
        """Converts an image content to a platform-specific image content."""
        pass

    @abstractmethod
    def convert_audio_content(self, content: PromptAudioContent) -> Any:
        """Converts an audio content to a platform-specific audio content."""
        pass

    @abstractmethod
    def convert_tool_use_content(self, content: PromptToolUseContent) -> Any:
        """Converts a tool use content to a platform-specific tool use content."""
        pass

    @abstractmethod
    def convert_tool_result_content(self, content: PromptToolResultContent) -> Any:
        """Converts a tool result content to a platform-specific tool result content."""
        pass

    @abstractmethod
    def convert_document_content(self, content: PromptDocumentContent) -> Any:
        """Converts a document content to a platform-specific document content."""
        pass

    def convert_content_item_to_platform_part(
        self,
        content: PromptMessageContent,
    ) -> Any:
        """Converts a content item to a platform-specific content item.

        Raises ValueError if unrecognized content.type.
        """
        ctype = content.kind
        if ctype == "text":
            return self.convert_text_content(content)
        elif ctype == "image":
            return self.convert_image_content(content)
        elif ctype == "audio":
            return self.convert_audio_content(content)
        elif ctype == "tool_use":
            return self.convert_tool_use_content(content)
        elif ctype == "tool_result":
            return self.convert_tool_result_content(content)
        else:
            raise ValueError(f"Unsupported PromptMessageContent type: {ctype}.")

    def convert_prompt_messages_to_platform_messages(
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
            parts.append(self.convert_content_item_to_platform_part(msg))
        return parts

    @abstractmethod
    async def convert_prompt(self, prompt: Prompt) -> PlatformPrompt:
        """Converts a prompt to a platform-specific prompt."""
        pass


class PlatformParsers(ABC, UsesKernelMixin):
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
class PlatformConfigs(UsesKernelMixin, Configuration):
    """A platform-specific configs."""

    supported_providers: list[ModelProvider] = field(
        default_factory=list,
        metadata={"description": "The supported providers for the platform."},
    )
    """The supported providers for the platform."""

    supported_models: list[Model] = field(
        default_factory=list,
        metadata={"description": "The supported models for the platform."},
    )
    """The supported models for the platform."""


class PlatformClient(ABC, UsesKernelMixin):
    """Provides a client to interact with a AI platform."""

    NAME: ClassVar[str] = ""

    def __init__(
        self,
        *,
        kernel: Kernel | None = None,
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
        self._parsers = self._init_parsers(kernel)
        self._configs = self._init_configs(kernel)

    def attach_kernel(self, kernel: Kernel) -> None:
        """Attach the kernel to the client."""
        super().attach_kernel(kernel)
        self._converters = self._converters.attach_kernel(kernel)
        self._parsers = self._parsers.attach_kernel(kernel)
        self._configs = self._configs.attach_kernel(kernel)

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
    def _init_converters(self, kernel: Kernel | None = None) -> PlatformConverters:
        """Initializes the platform-specific converters."""
        pass

    @abstractmethod
    def _init_parsers(self, kernel: Kernel | None = None) -> PlatformParsers:
        """Initializes the platform-specific parsers."""
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
    def _init_configs(self, kernel: Kernel | None = None) -> PlatformConfigs:
        """Initializes the platform-specific configs."""
        pass

    @abstractmethod
    async def generate_response(self, prompt: Prompt) -> ResponseMessage:
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
        prompt: Prompt,
    ) -> AsyncGenerator[ResponseMessage, None]:
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
