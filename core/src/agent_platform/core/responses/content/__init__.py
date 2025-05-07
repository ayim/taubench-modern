"""Content provided by the model."""

from agent_platform.core.responses.content.audio import ResponseAudioContent
from agent_platform.core.responses.content.base import ResponseMessageContent
from agent_platform.core.responses.content.document import ResponseDocumentContent
from agent_platform.core.responses.content.image import ResponseImageContent
from agent_platform.core.responses.content.text import ResponseTextContent
from agent_platform.core.responses.content.tool_use import ResponseToolUseContent

AnyResponseMessageContent = (
    ResponseAudioContent
    | ResponseDocumentContent
    | ResponseImageContent
    | ResponseTextContent
    | ResponseToolUseContent
)

__all__ = [
    "AnyResponseMessageContent",
    "ResponseAudioContent",
    "ResponseDocumentContent",
    "ResponseImageContent",
    "ResponseMessageContent",
    "ResponseTextContent",
    "ResponseToolUseContent",
]
