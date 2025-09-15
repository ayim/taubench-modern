from collections.abc import AsyncGenerator
from logging import getLogger
from typing import TYPE_CHECKING, Any

from agent_platform.core.delta import GenericDelta
from agent_platform.core.delta.compute_delta import compute_generic_deltas
from agent_platform.core.platforms.base import PlatformParsers
from agent_platform.core.responses.content import AnyResponseMessageContent
from agent_platform.core.responses.content.audio import ResponseAudioContent
from agent_platform.core.responses.content.image import ResponseImageContent
from agent_platform.core.responses.content.reasoning import ResponseReasoningContent
from agent_platform.core.responses.content.text import ResponseTextContent
from agent_platform.core.responses.content.tool_use import ResponseToolUseContent
from agent_platform.core.responses.response import ResponseMessage, TokenUsage

if TYPE_CHECKING:
    from openai.types.responses import (
        Response,
        ResponseCompletedEvent,
        ResponseFunctionCallArgumentsDeltaEvent,
        ResponseFunctionToolCall,
        ResponseInProgressEvent,
        ResponseOutputItemAddedEvent,
        ResponseOutputText,
        ResponseReasoningItem,
        ResponseReasoningSummaryPartAddedEvent,
        ResponseReasoningSummaryPartDoneEvent,
        ResponseReasoningSummaryTextDeltaEvent,
        ResponseReasoningSummaryTextDoneEvent,
        ResponseStreamEvent,
        ResponseTextDeltaEvent,
    )

logger = getLogger(__name__)


class OpenAIParsers(PlatformParsers):
    """Parsers that transform OpenAI types to agent-server prompt types."""

    def parse_text_content(
        self,
        content: "ResponseOutputText",
        parent_message_id: str | None = None,
    ) -> ResponseTextContent:
        """Parses a platform-specific text content to an agent-server
        text content.

        Args:
            content: The content to parse.

        Returns:
            The parsed text content.
        """
        metadata: dict[str, Any] = {
            "annotations": content.annotations,
            "logprobs": content.logprobs,
        }
        if parent_message_id is not None:
            metadata["provider_message_id"] = parent_message_id
        return ResponseTextContent(text=content.text, metadata=metadata)

    def parse_image_content(self, content: Any) -> ResponseImageContent:
        """Parses a platform-specific image content to an agent-server
        image content.

        Args:
            content: The content to parse.

        Returns:
            The parsed image content.
        """
        raise NotImplementedError("Image content not supported yet")

    def parse_audio_content(self, content: Any) -> ResponseAudioContent:
        """Parses a platform-specific audio content to an agent-server
        audio content.

        Args:
            content: The content to parse.

        Returns:
            The parsed audio content.
        """
        raise NotImplementedError("Audio content not supported yet")

    def parse_reasoning_content(self, content: "ResponseReasoningItem") -> ResponseReasoningContent:
        """Parses a platform-specific reasoning content to an agent-server
        reasoning content.
        """
        return ResponseReasoningContent(
            encrypted_content=content.encrypted_content,
            response_id=content.id,
            summary=[s.text for s in content.summary or []],
            content=[c.text for c in content.content or []],
            reasoning=None,
            signature=None,
            redacted_content=None,
        )

    def parse_tool_use_content(
        self,
        content: "ResponseFunctionToolCall",
    ) -> ResponseToolUseContent:
        """Parses a platform-specific tool use content to an agent-server
        tool use content.

        Args:
            content: The content to parse.

        Returns:
            The parsed tool use content.
        """
        from json import dumps

        # UNIQUE SCENARIO (encountered during further testing)
        # The reasoning models are producing weird tool call JSON
        # occasionally, I've seen a { function_name: { args... } }
        # which, of course, breaks...
        # It's unclear if we should handle this here... as you could
        # have a function named foo with an argument named foo...
        as_tool_use = ResponseToolUseContent(
            tool_call_id=content.call_id,
            tool_name=content.name,
            tool_input_raw=content.arguments,
            metadata={
                "status": content.status,
                "api_id": content.id,
            },
        )

        if as_tool_use.tool_name in as_tool_use.tool_input:
            logger.warning(
                "Tool name found in tool input: %s",
                as_tool_use.tool_name,
            )
            # If this is the _only_ key and it's a dict, we'll
            # "un-nest" the tool input
            all_keys = list(as_tool_use.tool_input.keys())
            if len(all_keys) == 1:
                content_at_name = as_tool_use.tool_input[all_keys[0]]
                if isinstance(content_at_name, dict):
                    logger.warning(
                        "Un-nesting tool input: %s",
                        content_at_name,
                    )
                    return ResponseToolUseContent(
                        tool_call_id=as_tool_use.tool_call_id,
                        tool_name=as_tool_use.tool_name,
                        tool_input_raw=dumps(content_at_name),
                    )

        return as_tool_use

    def parse_response(self, response: "Response") -> ResponseMessage:
        """Parses an OpenAI response to an agent-server response.

        Args:
            response: The OpenAI response to parse.

        Returns:
            A ResponseMessage containing the parsed content and raw response.

        Raises:
            ValueError: If the response format is invalid or missing required fields.
        """
        from openai.types.responses import (
            ResponseFunctionToolCall,
            ResponseOutputMessage,
            ResponseOutputText,
            ResponseReasoningItem,
        )

        mapped_content: list[AnyResponseMessageContent] = []
        for item in response.output:
            match item:
                case ResponseOutputMessage() as msg:
                    for content in msg.content:
                        match content:
                            case ResponseOutputText() as text:
                                mapped_content.append(self.parse_text_content(text, msg.id))
                            case _:
                                # Ignore unsupported content (refusals, etc.) for now
                                pass
                case ResponseFunctionToolCall() as tool_call:
                    mapped_content.append(self.parse_tool_use_content(tool_call))
                case ResponseReasoningItem() as reasoning:
                    mapped_content.append(self.parse_reasoning_content(reasoning))
                case _:
                    # Ignore unsupported output types (reasoning, builtin tools, etc.) for now
                    pass

        additional_fields: dict[str, Any] = {
            "id": response.id,
            "model": response.model,
        }

        return ResponseMessage(
            role="agent",
            content=mapped_content,
            usage=self._extract_token_usage(response),
            raw_response=response,
            additional_response_fields=additional_fields,
        )

    def _extract_token_usage(self, response: "Response") -> TokenUsage:
        """Extracts token usage from a response."""
        if not response.usage:
            return TokenUsage(
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                cached_tokens=0,
                reasoning_tokens=0,
            )

        usage = response.usage

        # Extract cached tokens from input_tokens_details
        cached_tokens = usage.input_tokens_details.cached_tokens

        # Extract reasoning tokens from output_tokens_details
        reasoning_tokens = usage.output_tokens_details.reasoning_tokens

        return TokenUsage(
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=usage.total_tokens,
            cached_tokens=cached_tokens,
            reasoning_tokens=reasoning_tokens,
        )

    async def parse_stream_event(  # noqa: PLR0912, C901
        self,
        event: "ResponseStreamEvent",
        message: dict[str, Any],
        last_message: dict[str, Any],
    ) -> AsyncGenerator[GenericDelta, None]:
        """Parses a single stream event from OpenAI into GenericDeltas."""
        from openai.types.responses import (
            ResponseCompletedEvent,
            ResponseFunctionCallArgumentsDeltaEvent,
            ResponseInProgressEvent,
            ResponseOutputItemAddedEvent,
            ResponseOutputItemDoneEvent,
            ResponseReasoningItem,
            ResponseReasoningSummaryPartAddedEvent,
            ResponseReasoningSummaryPartDoneEvent,
            ResponseReasoningSummaryTextDeltaEvent,
            ResponseReasoningSummaryTextDoneEvent,
            ResponseTextDeltaEvent,
        )

        # Initialize key parts of the message if they don't exist
        self._ensure_message_structure(message)
        # logger.info(f"Processing stream event: {event!r}")

        match event:
            case ResponseOutputItemAddedEvent() as e:
                self._process_output_item_added(e, message)
            case ResponseOutputItemDoneEvent() as e:
                match e.item:
                    case ResponseReasoningItem() as item:
                        self._process_reasoning_item_done(item, message)
                    case _:
                        pass
            case ResponseTextDeltaEvent() as e:
                self._process_text_delta(e, message)
            case ResponseFunctionCallArgumentsDeltaEvent() as e:
                self._process_function_args_delta(e, message)
            case ResponseInProgressEvent() as e:
                self._process_event_metadata(e, message)
            case ResponseCompletedEvent() as e:
                self._process_event_metadata(e, message)
            case ResponseReasoningSummaryTextDeltaEvent() as e:
                self._process_reasoning_summary_delta_or_done(e, message)
            case ResponseReasoningSummaryTextDoneEvent() as e:
                self._process_reasoning_summary_delta_or_done(e, message)
            case ResponseReasoningSummaryPartAddedEvent() as e:
                self._process_reasoning_summary_part_added(e, message)
            case ResponseReasoningSummaryPartDoneEvent() as e:
                self._process_reasoning_summary_part_done(e, message)
            case _:
                # logger.warning(f"Unhandled event: {event!r}")
                # Ignore other events for now
                pass

        # Calculate and yield deltas
        deltas = compute_generic_deltas(last_message, message)
        for delta in deltas:
            yield delta

    def _find_content(
        self,
        message: dict[str, Any],
        *,
        kind: str | None = None,
        predicate: Any | None = None,
        reverse: bool = False,
    ) -> dict[str, Any] | None:
        """Return the first content item (by reference) matching filters.

        Args:
            message: The message dict with a "content" list.
            kind: Optional content kind filter, e.g. "reasoning" or "tool_use".
            predicate: Optional callable taking a content dict -> bool.
            reverse: If True, search from the end of the list.
        """
        items = reversed(message["content"]) if reverse else message["content"]
        for content in items:
            if kind is not None and content.get("kind") != kind:
                continue
            if predicate is not None and not predicate(content):
                continue
            return content
        return None

    def _find_reasoning_content_by_item_id(
        self, message: dict[str, Any], item_id: str | None
    ) -> dict[str, Any] | None:
        if item_id is None:
            return None
        return self._find_content(
            message,
            kind="reasoning",
            predicate=lambda c: c.get("metadata", {}).get("provider_id") == item_id,
        )

    def _ensure_message_structure(self, message: dict[str, Any]) -> None:
        """Ensures the message has all required fields."""
        if "role" not in message:
            message["role"] = "agent"

        if "content" not in message:
            message["content"] = []

        # Collect values that don't directly map to ResponseMessage fields
        if "additional_response_fields" not in message:
            message["additional_response_fields"] = {}

    def _process_output_item_added(
        self,
        event: "ResponseOutputItemAddedEvent",
        message: dict[str, Any],
    ) -> None:
        """Processes an output item added event."""
        from openai.types.responses import (
            ResponseFunctionToolCall,
            ResponseOutputMessage,
            ResponseReasoningItem,
        )

        item = event.item

        # Assistant message scaffold; actual text arrives via text delta events
        if isinstance(item, ResponseOutputMessage):
            pass  # Nothing to do here

        elif isinstance(item, ResponseReasoningItem):
            message["content"].append(
                {
                    "kind": "reasoning",
                    "redacted_content": None,
                    "reasoning": None,
                    "signature": None,
                    "metadata": {"provider_id": item.id},
                    "encrypted_content": item.encrypted_content,
                    "response_id": item.id,
                    "summary": [s.text for s in item.summary or []],
                    "content": [c.text for c in item.content or []],
                }
            )

        # Function tool call: create a tool_use entry
        elif isinstance(item, ResponseFunctionToolCall):
            tool_call_id = item.call_id or ""
            tool_name = item.name or ""
            tool_args_initial = item.arguments or ""
            api_id = item.id

            tool_entry: dict[str, Any] = {
                "kind": "tool_use",
                "tool_call_id": tool_call_id,
                "tool_name": tool_name,
                "tool_input_raw": tool_args_initial,
            }
            if api_id is not None:
                tool_entry["metadata"] = {"api_id": api_id}

            message["content"].append(tool_entry)

        # Ignore other output item types for now
        else:
            return

    def _process_text_delta(
        self,
        event: "ResponseTextDeltaEvent",
        message: dict[str, Any],
    ) -> None:
        """Append streamed text to the message content."""
        delta_text = event.delta or ""
        if not delta_text:
            return

        # Find first existing text content and update by reference; otherwise create
        target = self._find_content(message, kind="text")
        if target is not None:
            target["text"] = (target.get("text") or "") + delta_text
            return

        message["content"].append({"kind": "text", "text": delta_text})

    def _process_function_args_delta(
        self,
        event: "ResponseFunctionCallArgumentsDeltaEvent",
        message: dict[str, Any],
    ) -> None:
        """Append streamed function call arguments to the correct tool_use entry."""
        delta_text = event.delta or ""
        item_id = event.item_id

        if not delta_text:
            return

        # Prefer matching by metadata.api_id if available
        target = None
        if item_id is not None:
            target = self._find_content(
                message,
                kind="tool_use",
                predicate=lambda c: (c.get("metadata") or {}).get("api_id") == item_id,
            )

        # Fallback: update the most recent tool_use
        if target is None:
            target = self._find_content(message, kind="tool_use", reverse=True)

        if target is not None:
            target["tool_input_raw"] = (target.get("tool_input_raw") or "") + delta_text
        return

    def _process_reasoning_summary_delta_or_done(
        self,
        event: "ResponseReasoningSummaryTextDeltaEvent | ResponseReasoningSummaryTextDoneEvent",
        message: dict[str, Any],
    ) -> None:
        """Append streamed reasoning summary text to the message content."""
        from openai.types.responses import ResponseReasoningSummaryTextDeltaEvent

        target = self._find_reasoning_content_by_item_id(message, event.item_id)
        if target is None:
            return

        summary: list[str] = target.setdefault("summary", [])
        idx = event.summary_index
        if idx >= len(summary):
            # New summary part; append the incoming text
            if isinstance(event, ResponseReasoningSummaryTextDeltaEvent):
                summary.append(event.delta)
            else:
                summary.append(event.text)
            return

        # Update existing summary part in-place
        if isinstance(event, ResponseReasoningSummaryTextDeltaEvent):
            summary[idx] += event.delta
        else:
            summary[idx] = event.text
        return

    def _process_reasoning_summary_part_done(
        self,
        event: "ResponseReasoningSummaryPartDoneEvent",
        message: dict[str, Any],
    ) -> None:
        """Processes a reasoning summary part done event."""
        target = self._find_reasoning_content_by_item_id(message, event.item_id)
        if target is None:
            return

        summary: list[str] = target.setdefault("summary", [])
        idx = event.summary_index
        if idx >= len(summary):
            summary.append(event.part.text)
        else:
            summary[idx] = event.part.text
        return

    def _process_reasoning_summary_part_added(
        self,
        event: "ResponseReasoningSummaryPartAddedEvent",
        message: dict[str, Any],
    ) -> None:
        """Processes a reasoning summary part added event."""
        target = self._find_reasoning_content_by_item_id(message, event.item_id)
        if target is None:
            return
        target.setdefault("summary", []).append(event.part.text)
        return

    def _process_reasoning_item_done(
        self,
        event: "ResponseReasoningItem",
        message: dict[str, Any],
    ) -> None:
        """Processes a reasoning item done event."""
        target = self._find_reasoning_content_by_item_id(message, event.id)
        if target is None:
            return

        target["encrypted_content"] = event.encrypted_content
        target["response_id"] = event.id
        target["summary"] = [s.text for s in (event.summary or [])]
        target["content"] = [c.text for c in (event.content or [])]
        return

    def _process_event_metadata(
        self,
        event: "ResponseInProgressEvent | ResponseCompletedEvent",
        message: dict[str, Any],
    ) -> None:
        """Processes metadata (id, model, usage) from in-progress or completed events."""
        # Both in_progress and completed events include a .response object
        response_obj = event.response

        # Basic identifiers
        message["additional_response_fields"]["id"] = response_obj.id
        message["additional_response_fields"]["model"] = response_obj.model

        # Token usage (typically present on completed)
        if response_obj.usage is not None:
            usage = response_obj.usage

            # Extract cached tokens from input_tokens_details
            cached_tokens = usage.input_tokens_details.cached_tokens

            # Extract reasoning tokens from output_tokens_details
            reasoning_tokens = usage.output_tokens_details.reasoning_tokens

            message["usage"] = {
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "total_tokens": usage.total_tokens,
                "cached_tokens": cached_tokens,
                "reasoning_tokens": reasoning_tokens,
            }
