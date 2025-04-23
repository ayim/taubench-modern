import json
import uuid
from collections.abc import AsyncGenerator
from logging import getLogger
from typing import Any

from google.genai.types import (
    Content,
    FunctionCall,
    GenerateContentResponse,
    GenerateContentResponseUsageMetadata,
)

from agent_platform.core.delta import GenericDelta
from agent_platform.core.delta.compute_delta import compute_generic_deltas
from agent_platform.core.platforms.base import PlatformParsers
from agent_platform.core.responses.content.audio import ResponseAudioContent
from agent_platform.core.responses.content.base import ResponseMessageContent
from agent_platform.core.responses.content.image import ResponseImageContent
from agent_platform.core.responses.content.text import ResponseTextContent
from agent_platform.core.responses.content.tool_use import ResponseToolUseContent
from agent_platform.core.responses.response import ResponseMessage, TokenUsage

logger = getLogger(__name__)


class GoogleParsers(PlatformParsers):
    """Parsers that transform Google types to agent-server prompt types."""

    def parse_text_content(self, content: str) -> ResponseTextContent:
        """Parses a platform-specific text content to an agent-server
        text content.

        Args:
            content: The content to parse.

        Returns:
            The parsed text content.
        """
        return ResponseTextContent(text=content)

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

    def parse_tool_use_content(
        self,
        function_call: dict[str, Any],
        tool_call_id: str = "",
    ) -> ResponseToolUseContent:
        """Parses a platform-specific tool use content to an agent-server
        tool use content.

        Args:
            function_call: The function call to parse.
            tool_call_id: Optional tool call ID.

        Returns:
            The parsed tool use content.
        """

        # If no ID is provided, generate a random one
        if not tool_call_id:
            tool_call_id = str(uuid.uuid4())

        # Format depends on the structure

        tool_name = function_call.get("name", "")
        args = function_call.get("args", {})

        # If args is already a dict, use it directly
        # Otherwise, if it's a string, try to parse it as JSON
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse tool input as JSON: {args}")

        return ResponseToolUseContent(
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            tool_input_raw=json.dumps(args) if isinstance(args, dict) else args,
        )

    def parse_response(self, response: GenerateContentResponse) -> ResponseMessage:
        """Parses a Google response to an agent-server response.

        Args:
            response: The Google response to parse.

        Returns:
            A ResponseMessage containing the parsed content and raw response.

        Raises:
            ValueError: If the response format is invalid or missing required fields.
        """
        response_content: list[ResponseMessageContent] = []

        # Extract the candidate (Google API returns candidates)
        if not response.candidates:
            raise ValueError("No candidates found in Google response")

        candidate = response.candidates[0]

        if not candidate.content:
            raise ValueError("No content found in candidate")

        if candidate.content.parts:
            for part in candidate.content.parts:
                # Text content
                if part.text:
                    response_content.append(self.parse_text_content(part.text))
                # Function call content
                elif part.function_call:
                    response_content.append(
                        self.parse_tool_use_content(
                            {
                                "name": part.function_call.name,
                                "args": part.function_call.args,
                            },
                        ),
                    )

        # Extract token usage information
        token_usage, thinking_tokens = self._extract_token_usage(response)
        thinking_tokens = 0 if thinking_tokens is None else thinking_tokens

        # Create the response message
        response_message = ResponseMessage(
            role="agent",
            content=response_content,
            usage=token_usage,
            raw_response=response,
        )

        # Store additional token metrics in metadata
        if thinking_tokens > 0:
            if "token_metrics" not in response_message.metadata:
                response_message.metadata["token_metrics"] = {}
            response_message.metadata["token_metrics"]["thinking_tokens"] = (
                thinking_tokens
            )

        return response_message

    def _extract_token_usage(
        self,
        response: GenerateContentResponse,
    ) -> tuple[TokenUsage, int]:
        """Extracts token usage from a response.

        Args:
            response: The Google response to extract token usage from.

        Returns:
            A tuple containing:
              - TokenUsage object with standard token metrics
              - thinking_tokens count as an integer
        """
        if not response.usage_metadata:
            return TokenUsage(input_tokens=0, output_tokens=0, total_tokens=0), 0

        usage_metadata = response.usage_metadata

        # Log all available token-related attributes for debugging
        logger.debug(f"Token usage metadata: {usage_metadata}")

        # Extract token counts
        input_tokens = usage_metadata.prompt_token_count or 0
        output_tokens = usage_metadata.candidates_token_count or 0
        total_tokens = usage_metadata.total_token_count
        if total_tokens is None:
            total_tokens = input_tokens + output_tokens
        thinking_tokens = usage_metadata.thoughts_token_count or 0

        # Log token usage
        self._log_token_usage(
            input_tokens,
            output_tokens,
            total_tokens,
            thinking_tokens,
            usage_metadata,
        )

        # Create TokenUsage object
        token_usage = TokenUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )

        return token_usage, thinking_tokens

    def _log_token_usage(
        self,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        thinking_tokens: int,
        usage_metadata: GenerateContentResponseUsageMetadata,
    ) -> None:
        """Log token usage details.

        Args:
            input_tokens: The input token count.
            output_tokens: The output token count.
            total_tokens: The total token count.
            thinking_tokens: The thinking token count.
            usage_metadata: The usage metadata.
        """
        # Log token usage summary
        logger.info(
            f"Extracted token usage: input={input_tokens}, output={output_tokens}, "
            f"total={total_tokens}, thinking={thinking_tokens}",
        )

        # Log detailed token breakdown if available
        self._log_input_token_details(usage_metadata)
        self._log_output_token_details(usage_metadata)

    def _log_input_token_details(
        self,
        usage_metadata: GenerateContentResponseUsageMetadata,
    ) -> None:
        """Log input token details by modality.

        Args:
            usage_metadata: The usage metadata.
        """
        prompt_tokens_details = usage_metadata.prompt_tokens_details
        if prompt_tokens_details:
            for detail in prompt_tokens_details:
                modality = detail.modality
                token_count = detail.token_count
                if modality is not None and token_count is not None:
                    logger.debug(
                        f"Input tokens by modality: {modality}={token_count}",
                    )

    def _log_output_token_details(
        self,
        usage_metadata: GenerateContentResponseUsageMetadata,
    ) -> None:
        """Log output token details by modality.

        Args:
            usage_metadata: The usage metadata.
        """
        candidates_tokens_details = usage_metadata.candidates_tokens_details
        if candidates_tokens_details:
            for detail in candidates_tokens_details:
                modality = detail.modality
                token_count = detail.token_count
                if modality is not None and token_count is not None:
                    logger.debug(
                        f"Output tokens by modality: {modality}={token_count}",
                    )

    async def parse_stream_event(
        self,
        event: GenerateContentResponse,
        message: dict[str, Any],
        last_message: dict[str, Any],
    ) -> AsyncGenerator[GenericDelta, None]:
        """Parses a single stream event from Google into GenericDeltas.

        Args:
            event: The streaming event from Google.
            message: The current message state.
            last_message: The previous message state.

        Yields:
            GenericDeltas that update the ResponseMessage.
        """
        # Initialize key parts of the message if they don't exist
        self._ensure_message_structure(message)

        candidates = event.candidates
        if candidates and len(candidates) > 0:
            candidate = candidates[0]
            if candidate.content:
                self._process_content(candidate.content, message)

            if candidate.finish_reason:
                message["stop_reason"] = candidate.finish_reason

        # Process metadata
        self._process_event_metadata(event, message)

        # Calculate and yield deltas
        deltas = compute_generic_deltas(last_message, message)
        for delta in deltas:
            yield delta

    def _ensure_message_structure(self, message: dict[str, Any]) -> None:
        """Ensures the message has all required fields."""
        if "role" not in message:
            message["role"] = "agent"

        if "content" not in message:
            message["content"] = []

        # Collect values that don't directly map to ResponseMessage fields
        if "additional_response_fields" not in message:
            message["additional_response_fields"] = {}

    def _process_content(self, content: Content, message: dict[str, Any]) -> None:
        """Processes content from a candidate."""
        if not content.parts:
            return

        # Collect content parts
        text_content, function_calls = self._collect_content_parts(content)

        # Process text content
        if text_content:
            self._add_text_content_to_message(message, text_content)

        # Process function calls
        if function_calls:
            self._add_function_calls_to_message(message, function_calls)

    def _collect_content_parts(self, content: Content) -> tuple[str, list[Any]]:
        """Collect text and function call content parts.

        Args:
            content: The content to process.

        Returns:
            A tuple containing text content and function calls.
        """
        text_content = ""
        function_calls = []

        if not content.parts:
            return text_content, function_calls

        for part in content.parts:
            # Direct access for text since it's a simple field
            if part.text:
                text_content += part.text
                continue

            function_call = part.function_call
            if function_call is not None:
                function_calls.append(function_call)
                logger.debug(f"Collected function call: {function_call}")

        return text_content, function_calls

    def _add_text_content_to_message(self, message: dict[str, Any], text: str) -> None:
        """Add text content to message.

        Args:
            message: The message to update.
            text: The text content to add.
        """
        # Find or create text content
        text_found = False
        for i, item in enumerate(message["content"]):
            if item.get("kind") == "text":
                message["content"][i]["text"] += text
                text_found = True
                break

        if not text_found:
            message["content"].append(
                {"kind": "text", "text": text},
            )

    def _add_function_calls_to_message(
        self,
        message: dict[str, Any],
        function_calls: list[Any],
    ) -> None:
        """Add function calls to message.

        Args:
            message: The message to update.
            function_calls: The function calls to add.
        """
        logger.debug(f"Processing {len(function_calls)} function calls in parallel")

        # Process each function call and add it to the message
        for function_call in function_calls:
            function_details = self._extract_function_details(function_call)

            # Check if this function call already exists
            if not self._function_exists_in_message(message, function_details):
                self._add_function_to_message(message, function_details)

    def _extract_function_details(self, function_call: FunctionCall) -> dict[str, Any]:
        """Extract function details.

        Args:
            function_call: The function call to extract details from.

        Returns:
            The extracted function details.
        """
        # Direct access since these are standard fields
        function_name = function_call.name or ""
        function_args = function_call.args or {}

        logger.debug(
            f"Processing function call: {function_name}, "
            f"args type: {type(function_args)}",
        )

        # Convert args to string if it's a dict
        if isinstance(function_args, dict):
            import json

            function_args_str = json.dumps(function_args)
        else:
            function_args_str = str(function_args)

        return {
            "name": function_name,
            "args_str": function_args_str,
        }

    def _function_exists_in_message(
        self,
        message: dict[str, Any],
        function_details: dict[str, Any],
    ) -> bool:
        """Check if function already exists in message.

        Args:
            message: The message to check.
            function_details: The function details to check for.

        Returns:
            Whether the function exists in the message.
        """
        for item in message["content"]:
            if (
                item.get("kind") == "tool_use"
                and item.get("tool_name") == function_details["name"]
                and item.get("tool_input_raw") == function_details["args_str"]
            ):
                return True

        return False

    def _add_function_to_message(
        self,
        message: dict[str, Any],
        function_details: dict[str, Any],
    ) -> None:
        """Add function to message.

        Args:
            message: The message to update.
            function_details: The function details to add.
        """
        # Create a new tool call entry with a unique ID
        import uuid

        message["content"].append(
            {
                "kind": "tool_use",
                "tool_call_id": str(uuid.uuid4()),
                "tool_name": function_details["name"],
                "tool_input_raw": function_details["args_str"],
            },
        )

        logger.debug(
            f"Added new tool call: {function_details['name']}"
            f"with args: {function_details['args_str']}",
        )

    def _process_event_metadata(
        self,
        event: GenerateContentResponse,
        message: dict[str, Any],
    ) -> None:
        """Processes metadata from the event."""
        if event.usage_metadata:
            self._process_usage_metadata(event.usage_metadata, message)

    def _process_usage_metadata(
        self,
        usage_metadata: GenerateContentResponseUsageMetadata,
        message: dict[str, Any],
    ) -> None:
        """Process usage metadata.

        Args:
            usage_metadata: The usage metadata to process.
            message: The message to update.
        """
        # Extract token counts
        token_counts = self._extract_token_counts(usage_metadata)

        # Log token usage
        logger.debug(
            f"Event token usage: input={token_counts['prompt']}, "
            f"output={token_counts['output']}, "
            f"total={token_counts['total']}, "
            f"thinking={token_counts['thinking']}",
        )

        # Update message usage information
        self._update_message_usage(message, token_counts)

        # Process detailed token information
        self._process_token_details(usage_metadata, message)

        # Log updated usage
        logger.debug(f"Updated message usage: {message.get('usage', {})}")

    def _extract_token_counts(self, usage_metadata: Any) -> dict[str, int]:
        """Extract token counts from usage metadata.

        Args:
            usage_metadata: The usage metadata.

        Returns:
            A dictionary of token counts.
        """
        # Extract basic token counts
        prompt_tokens = usage_metadata.prompt_token_count or 0
        output_tokens = usage_metadata.candidates_token_count or 0

        # Calculate total tokens
        total_tokens = usage_metadata.total_token_count
        if total_tokens is None:
            total_tokens = prompt_tokens + output_tokens

        # Extract thinking tokens
        thinking_tokens = usage_metadata.thoughts_token_count or 0

        # Ensure all token counts are valid integers
        prompt_tokens = 0 if prompt_tokens is None else prompt_tokens
        output_tokens = 0 if output_tokens is None else output_tokens
        total_tokens = 0 if total_tokens is None else total_tokens
        thinking_tokens = 0 if thinking_tokens is None else thinking_tokens

        return {
            "prompt": prompt_tokens,
            "output": output_tokens,
            "total": total_tokens,
            "thinking": thinking_tokens,
        }

    def _update_message_usage(
        self,
        message: dict[str, Any],
        token_counts: dict[str, int],
    ) -> None:
        """Update message usage information.

        Args:
            message: The message to update.
            token_counts: The token counts to add.
        """
        # Update core usage
        message["usage"] = {
            "input_tokens": token_counts["prompt"],
            "output_tokens": token_counts["output"],
            "total_tokens": token_counts["total"],
        }

        # Store thinking tokens in metadata if available
        if token_counts["thinking"] > 0:
            if "metadata" not in message:
                message["metadata"] = {}
            if "token_metrics" not in message["metadata"]:
                message["metadata"]["token_metrics"] = {}
            message["metadata"]["token_metrics"]["thinking_tokens"] = token_counts[
                "thinking"
            ]

    def _process_token_details(
        self,
        usage_metadata: GenerateContentResponseUsageMetadata,
        message: dict[str, Any],
    ) -> None:
        """Process detailed token information.

        Args:
            usage_metadata: The usage metadata containing token details.
            message: The message to update.
        """
        if not usage_metadata.prompt_tokens_details:
            return

        modality_tokens = {}
        for detail in usage_metadata.prompt_tokens_details:
            if detail.modality is not None:
                # Ensure token count is a valid integer
                token_count = detail.token_count or 0
                modality_tokens[str(detail.modality)] = token_count

        if modality_tokens:
            if "metadata" not in message:
                message["metadata"] = {}
            if "token_metrics" not in message["metadata"]:
                message["metadata"]["token_metrics"] = {}

            message["metadata"]["token_metrics"]["modality_tokens"] = modality_tokens
            logger.debug(f"Token usage by modality: {modality_tokens}")
