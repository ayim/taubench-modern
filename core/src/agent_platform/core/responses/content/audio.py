from base64 import b64decode
from dataclasses import dataclass, field
from typing import Literal

from agent_platform.core.responses.content.base import ResponseMessageContent
from agent_platform.core.utils import assert_literal_value_valid


@dataclass(kw_only=True)
class ResponseAudioContent(ResponseMessageContent):
    """Represents audio content generated or referenced in a model's response.

    This class handles audio content in various formats (URL, base64), supporting
    common audio formats like WAV and MP3. It provides validation for the audio data
    and ensures proper format handling.
    """

    mime_type: Literal["audio/wav", "audio/mp3"] = field(
        metadata={"description": "MIME type of the audio"},
    )
    """MIME type of the audio"""

    value: str = field(metadata={"description": "The base64 encoded audio data"})
    """The base64 encoded audio data"""

    kind: Literal["audio"] = field(
        default="audio",
        init=False,
        metadata={"description": "Content kind identifier, always 'audio'"},
    )
    """Content kind identifier, always 'audio'"""

    sub_type: Literal["base64", "url"] = field(
        default="base64",
        metadata={
            "description": "Format of the audio data - url-based or base64-encoded",
        },
    )
    """Format of the audio data - url-based or base64-encoded"""

    def __post_init__(self) -> None:
        """Validates the audio content after initialization.

        Performs validation of literal values and ensures the audio value is valid
        base64 data.

        Raises:
            AssertionError: If any literal fields don't match their expected values.
            ValueError: If the audio value is empty or if base64 data is invalid.
        """
        # Validate literal values
        assert_literal_value_valid(self, "kind")
        assert_literal_value_valid(self, "sub_type")
        assert_literal_value_valid(self, "mime_type")

        # Check for empty value
        if not self.value:
            raise ValueError("Audio value cannot be empty")

        # Validate base64 data
        if self.sub_type == "base64":
            try:
                b64decode(self.value, validate=True)
            except Exception as e:
                raise ValueError("Audio value is not a valid base64 string") from e

    def model_dump(self) -> dict:
        """Returns a dictionary representation suitable for serialization."""
        return {
            **super().model_dump(),
            "mime_type": self.mime_type,
            "value": self.value,
            "sub_type": self.sub_type,
        }

    @classmethod
    def model_validate(cls, data: dict) -> "ResponseAudioContent":
        """Create an audio content from a dictionary."""
        data = data.copy()
        # Remove 'kind' if present since it's not an init parameter
        if "kind" in data:
            data.pop("kind")
        return cls(**data)


ResponseMessageContent.register_content_kind("audio", ResponseAudioContent)
