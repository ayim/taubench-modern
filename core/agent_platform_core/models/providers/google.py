from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional, Union

from agent_server_types_v2.prompts import (
    Prompt,
    PromptAgentMessage,
    PromptAudioContent,
    PromptImageContent,
    PromptMessageContent,
    PromptTextContent,
    PromptToolResultContent,
    PromptToolUseContent,
    PromptUserMessage,
)
from agent_server_types_v2.prompts.base import PromptMessage
from agent_server_types_v2.utils.fetch import fetch_url_data

if TYPE_CHECKING:
    # For type-checking only. This ensures your library can refer to these
    # without forcing users to install `google-generativeai`.
    from google.generativeai import GenerationConfig
    from google.generativeai.protos import (
        FunctionCall,
        FunctionResponse,
    )
    from google.generativeai.types import (
        BlobDict,
        ContentDict,
        File,
        PartType,
    )


MAX_INLINE_BYTES = 10_000_000  # e.g. 10 MB threshold

# -------------------------------------------------------------------
# 1) Helpers for image/audio data retrieval
# -------------------------------------------------------------------


def _maybe_upload_if_large(
    raw_data: bytes,
    mime_type: str,
) -> Union["File", "BlobDict"]:
    """If `raw_data` exceeds MAX_INLINE_BYTES, upload to Gemini; otherwise
    return inline dict.

    Returns either a Gemini File object or inline dict: {"mime_type":..., "data":...}
    (BlobDict).
    """
    from google.generativeai.types import BlobDict

    data_size = len(raw_data)
    if data_size > MAX_INLINE_BYTES:
        # Do an on-demand import so we don't require the library for non-Gemini uses.
        from io import BytesIO

        import google.generativeai as genai

        # Create a file-like object from the bytes
        file_obj = BytesIO(raw_data)
        uploaded_file = genai.upload_file(file_obj, mime_type=mime_type)
        return uploaded_file
    else:
        return BlobDict(mime_type=mime_type, data=raw_data)


# -------------------------------------------------------------------
# 2) Converters for each content type
# -------------------------------------------------------------------


def _convert_text_content(content_item: PromptTextContent) -> str:
    """Convert PromptTextContent to a plain string for Gemini."""
    txt = content_item.text.strip()
    if not txt:
        raise ValueError("Encountered empty text content; cannot convert to Gemini.")
    return txt


def _convert_image_content(
    content_item: PromptImageContent,
) -> Union["File", "BlobDict"]:
    """Converts PromptImageContent into a Gemini-compatible object.

    Follows the following logic:
      - If sub_type="url", fetches data from the URL.
      - If sub_type="base64", decodes from base64.
      - Then either inlines or uploads, if large.
    """
    from base64 import b64decode

    if content_item.sub_type == "url":
        if not content_item.value:
            raise ValueError("Empty image URL encountered, cannot convert.")
        raw_data = fetch_url_data(content_item.value)
        return _maybe_upload_if_large(raw_data, content_item.mime_type)

    elif content_item.sub_type == "base64":
        if not content_item.value:
            raise ValueError("Empty image base64 encountered, cannot convert.")
        raw_data = b64decode(content_item.value, validate=True)
        return _maybe_upload_if_large(raw_data, content_item.mime_type)

    elif content_item.sub_type == "raw_bytes":
        if not content_item.value:
            raise ValueError("Empty image raw_bytes encountered, cannot convert.")
        return _maybe_upload_if_large(content_item.value, content_item.mime_type)

    else:
        raise ValueError(f"Unsupported image sub_type: {content_item.sub_type}")


def _convert_audio_content(
    content_item: PromptAudioContent,
) -> Union["File", "BlobDict"]:
    """Converts PromptAudioContent into Gemini-compatible object.

    Follows the following logic:
      - If sub_type="url", fetch data from the URL
      - If sub_type="base64", decode from base64
      - Then either inline or upload, if large
    """
    from base64 import b64decode

    if not content_item.value:
        raise ValueError("Empty audio content encountered, cannot convert.")

    if content_item.sub_type == "url":
        raw_data = fetch_url_data(content_item.value)
    elif content_item.sub_type == "base64":
        raw_data = b64decode(content_item.value, validate=True)
    else:
        raise ValueError(f"Unsupported audio sub_type: {content_item.sub_type}")

    return _maybe_upload_if_large(raw_data, content_item.mime_type)


def _convert_tool_use_content(content_item: PromptToolUseContent) -> "FunctionCall":
    """Converts PromptToolUseContent into a Gemini function_call."""
    from google.generativeai.protos import FunctionCall

    if not content_item.tool_name:
        raise ValueError("ToolUse missing tool_name; cannot convert to function_call.")
    return FunctionCall(
        name=content_item.tool_name,
        args=content_item.tool_input,
    )


def _convert_tool_result_content(
    content_item: PromptToolResultContent,
) -> "FunctionResponse":
    """Converts PromptToolResultContent into a Gemini function_response."""
    from google.generativeai.protos import FunctionResponse

    if not content_item.tool_name:
        raise ValueError(
            "ToolResult missing tool_name; cannot convert to function_response.",
        )

    # Build a JSON-like 'response' object
    # TODO: is this the "ideal" tool-response format? Worth some testing
    response_data = {
        "is_error": content_item.is_error,
        "call_id": content_item.tool_call_id,
        "outputs": [],
    }

    for sub in content_item.content:
        if isinstance(sub, PromptTextContent):
            response_data["outputs"].append({"type": "text", "data": sub.text})
        else:
            # TODO: image outputs? (Doesn't have the special handling like Anthropic)
            raise ValueError(
                f"Unsupported sub-content in tool_result: {sub.type}. "
                "Extend logic if you want more detail.",
            )

    return FunctionResponse(
        name=content_item.tool_name,
        response=response_data,
    )


# -------------------------------------------------------------------
# 3) Master "content item" converter
# -------------------------------------------------------------------


def convert_content_item_to_gemini_part(
    content_item: PromptMessageContent,
) -> "PartType":
    """Dispatches to the correct specialized converter.

    Raises ValueError if unrecognized content_item.type.
    """
    ctype = content_item.kind
    if ctype == "text":
        return _convert_text_content(content_item)
    elif ctype == "image":
        return _convert_image_content(content_item)
    elif ctype == "audio":
        return _convert_audio_content(content_item)
    elif ctype == "tool_use":
        return _convert_tool_use_content(content_item)
    elif ctype == "tool_result":
        return _convert_tool_result_content(content_item)
    else:
        raise ValueError(f"Unsupported PromptMessageContent type: {ctype}.")


# -------------------------------------------------------------------
# 4) Messages -> history
# -------------------------------------------------------------------


def convert_prompt_messages_to_gemini_history(
    messages: list[PromptMessage],
) -> list["ContentDict"]:
    """Converts each PromptUserMessage or PromptAgentMessage to a Gemini 'history' item.

    For example:
      {"role": "user", "parts": [...]}
      {"role": "model","parts": [...]}
    """
    from google.generativeai.types import ContentDict

    history = []
    for msg in messages:
        if isinstance(msg, PromptUserMessage):
            gemini_role = "user"
        elif isinstance(msg, PromptAgentMessage):
            gemini_role = "model"
        else:
            raise ValueError(f"Unknown message role or type: {type(msg)}")

        parts: list[PartType] = []
        for content_item in msg.content:
            gemini_part = convert_content_item_to_gemini_part(content_item)
            parts.append(gemini_part)

        history.append(ContentDict(role=gemini_role, parts=parts))

    return history


# -------------------------------------------------------------------
# 5) Top-level converter from Prompt -> dict for Gemini usage
# -------------------------------------------------------------------


@dataclass(frozen=True)
class GeminiParams:
    """Parameters for Gemini chat sessions."""

    message: "ContentDict" = field(
        metadata={"description": "Latest user message to send to Gemini."},
    )
    """Latest user message to send to Gemini."""
    system_instruction: str = field(
        default="",
        metadata={"description": "System instruction to provide to Gemini."},
    )
    """System instruction to provide to Gemini."""
    history: list["ContentDict"] = field(
        default_factory=list,
        metadata={"description": "History of messages to create Gemini chat history."},
    )
    """History of messages to create Gemini chat history."""
    generation_config: Optional["GenerationConfig"] = field(
        default=None,
        metadata={"description": "Generation config to use for Gemini."},
    )
    """Generation config to use for Gemini."""


def convert_prompt_to_gemini_dict(prompt: Prompt) -> GeminiParams:
    """Converts our top-level Prompt type to a Gemini-compatible dict.

    Converts a top-level Prompt to a dictionary with keys:
       "system_instruction", "history", "generation_config"
    which can be used to initialize a Gemini chat session.

    We only type-hint Gemini objects if TYPE_CHECKING is True, so
    consumers don't need the google-generativeai library installed.
    """
    from google.generativeai import GenerationConfig
    from google.generativeai.types import ContentDict

    # Convert history
    history = convert_prompt_messages_to_gemini_history(prompt.messages)

    # Build generation_config
    generation_config = GenerationConfig()

    # SEED is NOT supported by Google AI Studio... only by Vertex;
    # confusing, I know.
    # if prompt.seed is not None:
    #     generation_config.seed = prompt.seed

    if prompt.temperature is not None:
        generation_config.temperature = prompt.temperature
    if prompt.top_p is not None:
        generation_config.top_p = prompt.top_p
    if prompt.stop_sequences is not None:
        generation_config.stop_sequences = prompt.stop_sequences
    if prompt.max_output_tokens is not None:
        generation_config.max_output_tokens = prompt.max_output_tokens

    if len(history) > 0:
        message = history[-1]
        history = history[:-1]
    else:
        message = ContentDict(role="user", parts=[])

    return GeminiParams(
        system_instruction=prompt.system_instruction,
        message=message,
        history=history,
        generation_config=generation_config,
    )
