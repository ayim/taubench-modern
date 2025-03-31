"""OpenAI platform configurations."""

from dataclasses import dataclass, field
from typing import Any, ClassVar

from agent_platform.core.platforms.base import PlatformConfigs


@dataclass(frozen=True)
class OpenAIModelMap:
    """OpenAI model mapping."""

    model_id: str
    """OpenAI model ID"""

    model_name: str
    """OpenAI model name"""

    context_window: int
    """Context window size"""

    max_tokens: int
    """Maximum tokens per request"""

    supports_functions: bool = field(default=False)
    """Whether the model supports function calling"""

    supports_vision: bool = field(default=False)
    """Whether the model supports vision"""

    supports_audio: bool = field(default=False)
    """Whether the model supports audio"""


@dataclass(frozen=True)
class OpenAIContentLimits:
    """OpenAI content limits."""

    max_tokens: int = field(default=4096)
    """Maximum tokens per request"""

    max_tokens_per_message: int = field(default=4096)
    """Maximum tokens per message"""

    max_messages: int = field(default=100)
    """Maximum number of messages"""

    max_tools: int = field(default=10)
    """Maximum number of tools"""

    max_tool_calls: int = field(default=10)
    """Maximum number of tool calls per request"""


@dataclass(frozen=True)
class OpenAIMimeTypeMap:
    """OpenAI MIME type mapping."""

    mime_type: str
    """MIME type"""

    content_type: str
    """OpenAI content type"""


@dataclass(frozen=True)
class OpenAIPlatformConfigs(PlatformConfigs):
    """OpenAI platform configurations."""

    _model_maps: ClassVar[dict[str, OpenAIModelMap]] = {
        "gpt-4": OpenAIModelMap(
            model_id="gpt-4",
            model_name="GPT-4",
            context_window=8192,
            max_tokens=4096,
            supports_functions=True,
        ),
        "gpt-4-turbo": OpenAIModelMap(
            model_id="gpt-4-turbo-preview",
            model_name="GPT-4 Turbo",
            context_window=128000,
            max_tokens=4096,
            supports_functions=True,
            supports_vision=True,
        ),
        "gpt-3.5-turbo": OpenAIModelMap(
            model_id="gpt-3.5-turbo",
            model_name="GPT-3.5 Turbo",
            context_window=16385,
            max_tokens=4096,
            supports_functions=True,
        ),
    }

    _content_limits: ClassVar[OpenAIContentLimits] = OpenAIContentLimits()

    _mime_type_maps: ClassVar[list[OpenAIMimeTypeMap]] = [
        OpenAIMimeTypeMap(mime_type="image/jpeg", content_type="image_url"),
        OpenAIMimeTypeMap(mime_type="image/png", content_type="image_url"),
        OpenAIMimeTypeMap(mime_type="image/gif", content_type="image_url"),
        OpenAIMimeTypeMap(mime_type="image/webp", content_type="image_url"),
        OpenAIMimeTypeMap(mime_type="image/heic", content_type="image_url"),
        OpenAIMimeTypeMap(mime_type="image/heif", content_type="image_url"),
        OpenAIMimeTypeMap(mime_type="audio/mpeg", content_type="audio_url"),
        OpenAIMimeTypeMap(mime_type="audio/wav", content_type="audio_url"),
        OpenAIMimeTypeMap(mime_type="audio/ogg", content_type="audio_url"),
        OpenAIMimeTypeMap(mime_type="audio/webm", content_type="audio_url"),
    ]

    supported_models_by_provider: dict[str, list[str]] = field(
        default_factory=lambda: {
            "openai": [
                "gpt-4",
                "gpt-4-turbo",
                "gpt-3.5-turbo",
            ],
        },
        metadata={"description": "The supported models by provider."},
    )
    """The supported models by provider."""

    @property
    def model_maps(self) -> dict[str, OpenAIModelMap]:
        """Get model mappings."""
        return self._model_maps

    @property
    def content_limits(self) -> OpenAIContentLimits:
        """Get content limits."""
        return self._content_limits

    @property
    def mime_type_maps(self) -> list[OpenAIMimeTypeMap]:
        """Get MIME type mappings."""
        return self._mime_type_maps

    @property
    def default_model(self) -> str:
        """Get default model."""
        return "gpt-4-turbo"

    @property
    def supported_features(self) -> dict[str, Any]:
        """Get supported features."""
        return {
            "functions": True,
            "vision": True,
            "audio": True,
            "streaming": True,
        }
