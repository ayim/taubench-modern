import base64
import json
from dataclasses import FrozenInstanceError

import pytest

from agent_platform.core.responses.content.audio import ResponseAudioContent


class TestResponseAudioContent:
    """Tests for the ResponseAudioContent class."""

    @pytest.fixture
    def valid_base64_audio(self) -> str:
        """Create a valid base64 string for testing."""
        # This is just a simple base64 encoded string, not actual audio data
        return base64.b64encode(b"test audio data").decode("utf-8")

    def test_init(self, valid_base64_audio: str) -> None:
        """Test that ResponseAudioContent initializes correctly."""
        content = ResponseAudioContent(
            mime_type="audio/wav",
            value=valid_base64_audio,
        )
        assert content.mime_type == "audio/wav"
        assert content.value == valid_base64_audio
        assert content.kind == "audio"
        assert content.sub_type == "base64"

    def test_init_with_sub_type(self, valid_base64_audio: str) -> None:
        """Test that ResponseAudioContent initializes with a sub_type."""
        content = ResponseAudioContent(
            mime_type="audio/wav",
            value=valid_base64_audio,
            sub_type="base64",
        )
        assert content.mime_type == "audio/wav"
        assert content.value == valid_base64_audio
        assert content.kind == "audio"
        assert content.sub_type == "base64"

    def test_init_with_url_sub_type(self) -> None:
        """Test that ResponseAudioContent initializes with a url sub_type."""
        content = ResponseAudioContent(
            mime_type="audio/wav",
            value="https://example.com/audio.wav",
            sub_type="url",
        )
        assert content.mime_type == "audio/wav"
        assert content.value == "https://example.com/audio.wav"
        assert content.kind == "audio"
        assert content.sub_type == "url"

    def test_init_empty_value(self) -> None:
        """Test that ResponseAudioContent raises an error for empty value."""
        with pytest.raises(ValueError, match="Audio value cannot be empty"):
            ResponseAudioContent(
                mime_type="audio/wav",
                value="",
            )

    def test_init_invalid_base64(self) -> None:
        """Test that ResponseAudioContent raises an error for invalid base64."""
        with pytest.raises(
            ValueError,
            match="Audio value is not a valid base64 string",
        ):
            ResponseAudioContent(
                mime_type="audio/wav",
                value="invalid base64!",
                sub_type="base64",
            )

    def test_model_dump(self, valid_base64_audio: str) -> None:
        """Test that model_dump returns a dictionary with the audio data."""
        content = ResponseAudioContent(
            mime_type="audio/wav",
            value=valid_base64_audio,
        )
        data = content.model_dump()
        assert data["kind"] == "audio"
        assert data["mime_type"] == "audio/wav"
        assert data["value"] == valid_base64_audio
        assert data["sub_type"] == "base64"

    def test_model_dump_json(self, valid_base64_audio: str) -> None:
        """Test that model_dump_json returns a JSON string."""
        content = ResponseAudioContent(
            mime_type="audio/wav",
            value=valid_base64_audio,
        )
        json_str = content.model_dump_json()
        assert isinstance(json_str, str)
        data = json.loads(json_str)
        assert data["kind"] == "audio"
        assert data["mime_type"] == "audio/wav"
        assert data["value"] == valid_base64_audio
        assert data["sub_type"] == "base64"

    def test_model_validate(self, valid_base64_audio: str) -> None:
        """Test that model_validate creates a ResponseAudioContent from a dictionary."""
        data = {
            "kind": "audio",
            "mime_type": "audio/wav",
            "value": valid_base64_audio,
            "sub_type": "base64",
        }
        init_data = data.copy()
        init_data.pop("kind")
        content = ResponseAudioContent.model_validate(init_data)

        assert isinstance(content, ResponseAudioContent)
        assert content.kind == "audio"
        assert content.mime_type == "audio/wav"
        assert content.value == valid_base64_audio
        assert content.sub_type == "base64"

    def test_immutability(self, valid_base64_audio: str) -> None:
        """Test that ResponseAudioContent is immutable."""
        content = ResponseAudioContent(
            mime_type="audio/wav",
            value=valid_base64_audio,
        )
        with pytest.raises(FrozenInstanceError):
            # This should raise an exception because ResponseAudioContent is frozen
            content.mime_type = "audio/mp3"  # type: ignore
