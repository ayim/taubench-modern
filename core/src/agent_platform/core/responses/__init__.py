"""Response types from language models.

This module defines the types that represent responses/outputs from language
models. These types are part of a critical cycle in the agent architecture
that transforms messages between different representations as they flow through
the system:

1. Thread Messages (Thread*) - Represent the state of conversation between user and
    agent architecture
2. Prompt Messages (Prompt*) - Represent the input format sent to language models
3. Response Messages (Response*) - Represent the output format received from
    language models

The typical flow of messages through the system follows this cycle:

    User Input -> Thread* -> Prompt* -> LLM -> Response* -> Thread* -> Agent Output

Key responsibilities in this cycle:
- The model's role is to transform Prompt* messages into Response* messages
- The agent architecture's role is to:
  a) Transform Response* messages into Thread* messages (for state updates)
  b) Transform Thread* messages back into Prompt* messages (for next model call)

Response types capture both the core message content (text, images, tool calls
etc.) as well as model-specific metadata like usage statistics, stop reasons,
and other platform-specific outputs that don't map directly to prompt message types.

This explicit separation of concerns between Thread*, Prompt* and Response*
types helps maintain clean architectural boundaries while supporting the full range
of multi-modal inputs/outputs (text, documents, images, audio) and
platform-specific features.

Implementation Design:
The response types are implemented with the following principles:
1. Model-agnostic while supporting provider-specific features via
    additional_response_fields
2. Strongly typed with clear validation rules for each content type
3. Immutable (frozen) dataclasses to prevent accidental modifications
4. Standardized metadata structure:
   - usage: Token statistics tracked via TokenUsage class
   - metrics: Performance and timing information
   - metadata: Additional response generation context
5. Multi-modal content support through specialized content classes
6. Consistent validation and error handling across all types
"""

from agent_platform.core.responses.content import (
    ResponseAudioContent,
    ResponseDocumentContent,
    ResponseImageContent,
    ResponseMessageContent,
    ResponseTextContent,
    ResponseToolUseContent,
)
from agent_platform.core.responses.response import ResponseMessage, TokenUsage

__all__ = [
    "ResponseAudioContent",
    "ResponseDocumentContent",
    "ResponseImageContent",
    "ResponseMessage",
    "ResponseMessageContent",
    "ResponseTextContent",
    "ResponseToolUseContent",
    "TokenUsage",
]
