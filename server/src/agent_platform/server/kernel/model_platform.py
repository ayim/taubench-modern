import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from agent_platform.core.kernel import Kernel
from agent_platform.core.kernel_interfaces.model_platform import PlatformInterface
from agent_platform.core.platforms.base import PlatformClient
from agent_platform.core.prompts import Prompt
from agent_platform.core.prompts.content import (
    PromptTextContent,
    PromptToolResultContent,
    PromptToolUseContent,
)
from agent_platform.core.prompts.messages import PromptUserMessage
from agent_platform.core.responses import ResponseMessage, TokenUsage
from agent_platform.core.responses.streaming import ResponseStreamPipe
from agent_platform.server.kernel.kernel_mixin import UsesKernelMixin

logger = logging.getLogger(__name__)


class AgentServerPlatformInterface(PlatformInterface, UsesKernelMixin):
    """Provides interface for interacting with the agent's configured LLM."""

    def __init__(self, internal_client: PlatformClient):
        self._internal_client = internal_client

    def attach_kernel(self, kernel: Kernel) -> None:
        """Attach the kernel to the platform interface."""
        super().attach_kernel(kernel)
        self._internal_client.attach_kernel(kernel)

    @property
    def name(self) -> str:
        """The name of the platform."""
        return self._internal_client.name

    @property
    def client(self) -> PlatformClient:
        """The client for the platform."""
        return self._internal_client

    async def generate_response(
        self,
        prompt: Prompt,
        model: str,
    ) -> ResponseMessage:
        """Generates a response to a prompt.

        Arguments:
            prompt: The prompt to generate a response for.
            model: The model to use to generate the response.

        Returns:
            The generated model response.
        """
        with self.kernel.ctx.start_span(
            "generate_response",
            attributes={
                "agent_id": self.kernel.agent.agent_id,
                "thread_id": self.kernel.thread.thread_id,
                "llm.model": model,
                "llm.provider": self._internal_client.name,
            },
        ):
            # Use the default finalizers chain defined in Prompt.finalize_messages
            # (SpecialMessageFinalizer followed by TruncationFinalizer).
            finalized_prompt = await prompt.finalize_messages(
                self.kernel,
                platform=self,
                model=model,
            )

            # Record tools in trace directly from the finalized_prompt
            if finalized_prompt.tools:
                self.kernel.prompts.record_tools_in_trace(
                    finalized_prompt, span_name="generate_response_tools"
                )

            # Convert prompt for the specific platform
            converted_prompt = await self._internal_client.converters.convert_prompt(
                finalized_prompt,
                model_id=model,
            )

            try:
                inputs = self._create_langsmith_inputs_from_prompt(finalized_prompt)

                metadata = self._generate_metadata(model)

                async with self.kernel.ctx.langsmith.trace_llm(
                    name="llm_completion",
                    inputs=inputs,
                    user_context=self.kernel.ctx.user_context,
                    metadata=metadata,
                ) as langsmith_span:
                    # Make the actual API call
                    response = await self._internal_client.generate_response(
                        converted_prompt,
                        model,
                    )
                    if langsmith_span:
                        langsmith_span["output"] = (
                            self.kernel.ctx.langsmith.format_response_for_langsmith(response)
                        )

                        # Add usage information if available
                        if response.metadata:
                            usage = response.metadata.get("usage", {})
                            if usage and langsmith_span:
                                langsmith_span["usage"] = self._generate_usage_metadata(usage)

                    return response
            except Exception:
                return await self._internal_client.generate_response(
                    converted_prompt,
                    model,
                )

    @asynccontextmanager
    async def stream_response(
        self,
        prompt: Prompt,
        model: str,
    ) -> AsyncIterator[ResponseStreamPipe]:
        """Streams a response to a prompt as a context manager.

        Arguments:
            prompt: The prompt to generate a response for.
            model: The model to use to generate the response.

        Returns:
            An async context manager that yields a ResponseStreamPipe
            object managing the response stream.
        """
        with self.kernel.ctx.start_span(
            "stream_response",
            attributes={
                "agent_id": self.kernel.agent.agent_id,
                "thread_id": self.kernel.thread.thread_id,
                "llm.model": model,
                "llm.provider": self._internal_client.name,
                "streaming": True,
            },
        ):
            # Use the default finalizers chain defined in Prompt.finalize_messages
            # (SpecialMessageFinalizer followed by TruncationFinalizer).
            finalized_prompt = await prompt.finalize_messages(
                self.kernel,
                platform=self,
                model=model,
            )

            # Record tools in trace directly from the finalized_prompt
            if finalized_prompt.tools:
                self.kernel.prompts.record_tools_in_trace(
                    finalized_prompt, span_name="stream_response_tools"
                )

            # Convert the prompt for the platform
            converted_prompt = await self._internal_client.converters.convert_prompt(
                finalized_prompt,
                model_id=model,
            )

            # Initialize the response stream
            response_stream = self._internal_client.generate_stream_response(
                converted_prompt,
                model,
            )

            # Create the stream pipe
            stream_pipe = ResponseStreamPipe(response_stream, finalized_prompt)

            # LangSmith context for tracing (will be None if unavailable)
            langsmith_span = None

            # Try to set up LangSmith tracing if available
            try:
                inputs = self._create_langsmith_inputs_from_prompt(finalized_prompt)

                # Set up metadata
                metadata = self._generate_metadata(model, streaming=True)

                async with self.kernel.ctx.langsmith.trace_llm(
                    name="llm_stream_completion",
                    inputs=inputs,
                    user_context=self.kernel.ctx.user_context,
                    metadata=metadata,
                ) as langsmith_span:
                    try:
                        # Yield the stream pipe to let the caller use it
                        yield stream_pipe
                    finally:
                        # First close the stream
                        await stream_pipe.aclose()

                        # Record the response in LangSmith if available
                        if stream_pipe.reassembled_response:
                            # Format the response for LangSmith
                            formatted_response = (
                                self.kernel.ctx.langsmith.format_response_for_langsmith(
                                    stream_pipe.reassembled_response
                                )
                            )
                            if langsmith_span:
                                langsmith_span["output"] = formatted_response

                            # Add usage information if available
                            if stream_pipe.reassembled_response.usage:
                                usage = stream_pipe.reassembled_response.usage
                                labels = {
                                    "llm.model": model,
                                    "llm.provider": self._internal_client.name,
                                    "agent_id": self.kernel.agent.agent_id,
                                    "thread_id": self.kernel.thread.thread_id,
                                    "agent_name": self.kernel.agent.name,
                                    "thread_name": self.kernel.thread.name,
                                }
                                self.kernel.ctx.increment_counter(
                                    name="sema4ai.agent_server.prompt_tokens",
                                    increment=usage.input_tokens,
                                    labels=labels,
                                )
                                self.kernel.ctx.increment_counter(
                                    name="sema4ai.agent_server.completion_tokens",
                                    increment=usage.output_tokens,
                                    labels=labels,
                                )
                                self.kernel.ctx.increment_counter(
                                    name="sema4ai.agent_server.total_tokens",
                                    increment=usage.total_tokens,
                                    labels=labels,
                                )
                                if usage and langsmith_span:
                                    langsmith_span["usage"] = self._generate_usage_metadata(usage)
            except Exception:
                # If LangSmith setup fails or is not available, continue without tracing
                try:
                    # Yield the stream pipe to let the caller use it
                    yield stream_pipe
                finally:
                    # Close the stream
                    await stream_pipe.aclose()

    async def count_tokens(self, prompt: Prompt, model: str) -> int:
        """Count the tokens in a prompt.

        Args:
            prompt: The prompt to count the tokens of.
            model: The model to use to count the tokens.

        Returns:
            The number of tokens in the prompt.
        """
        return await self._internal_client.count_tokens(prompt, model)

    def _generate_metadata(self, model, streaming: bool = False) -> dict[str, Any]:
        metadata = {
            "model": model,
            "provider": self._internal_client.name,
            "trace_name": f"stream_response_{self._internal_client.name}",
            "streaming": streaming,
            "agent_id": self.kernel.agent.agent_id,
            "thread_id": self.kernel.thread.thread_id,
            "agent_name": self.kernel.agent.name,
            "user_id": self.kernel.user.user_id,
            "organization": (
                self.kernel.user.cr_tenant_id if self.kernel.user.cr_tenant_id else "unknown"
            ),
        }
        return metadata

    def _generate_usage_metadata(self, usage: TokenUsage) -> dict[str, Any]:
        usage_metadata = {
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
            "total_tokens": usage.total_tokens,
        }
        return usage_metadata

    def _create_langsmith_inputs_from_prompt(self, finalized_prompt: Prompt) -> dict[str, Any]:
        """Create standardized LangSmith inputs from a finalized prompt.

        Args:
            finalized_prompt: The finalized prompt with all messages and components

        Returns:
            A dictionary with inputs formatted for LangSmith tracing
        """
        inputs = {}
        messages = []

        if finalized_prompt.system_instruction:
            inputs["system"] = finalized_prompt.system_instruction
            messages.append({"role": "system", "content": finalized_prompt.system_instruction})

        messages = self._process_messages(finalized_prompt, messages)

        inputs["messages"] = json.dumps(messages)

        return inputs

    def _process_messages(
        self, finalized_prompt: Prompt, messages: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Process all messages in the prompt and extract tool calls and results."""
        # Process each message in sequence
        for i, msg in enumerate(finalized_prompt.finalized_messages):
            # Skip empty user messages
            if isinstance(msg, PromptUserMessage) and not msg.content:
                continue

            role = "user" if isinstance(msg, PromptUserMessage) else "assistant"

            # Process message content and extract tool calls
            content_parts = []
            tool_calls = []
            tool_call_ids = []

            for content_item in msg.content:
                # Text content
                if isinstance(content_item, PromptTextContent) and content_item.text:
                    content_parts.append(content_item.text)

                # Tool use content - capture tool calls
                elif isinstance(content_item, PromptToolUseContent) and content_item.tool_name:
                    tool_call = self._extract_tool_call(content_item)
                    if tool_call:
                        tool_calls.append(tool_call)
                        tool_call_ids.append(content_item.tool_call_id)

            # Create the message entry
            message_data = {"role": role}

            # Add content as joined text if we have text parts
            if content_parts:
                message_data["content"] = "\n".join(content_parts)

            # Add tool calls if present
            if tool_calls:
                message_data["tool_calls"] = json.dumps(tool_calls)

            # Add the message to our list
            messages.append(message_data)

            # Process tool results if this was an assistant message with tool calls
            if role == "assistant" and tool_call_ids:
                messages = self._process_tool_results(finalized_prompt, messages, i, tool_call_ids)

        return messages

    def _extract_tool_call(self, content_item: PromptToolUseContent) -> dict[str, Any] | None:
        """Extract tool call information from a PromptToolUseContent item."""
        try:
            # Create tool call entry
            tool_input_str = (
                str(content_item.tool_input_raw) if content_item.tool_input_raw else "{}"
            )

            return {
                "id": content_item.tool_call_id,
                "type": "function",
                "function": {
                    "name": content_item.tool_name,
                    "arguments": tool_input_str,
                },
            }
        except Exception as e:
            logger.warning(f"Error processing tool call: {e}")
            return None

    def _process_tool_results(
        self,
        finalized_prompt: Prompt,
        messages: list[dict[str, Any]],
        assistant_msg_index: int,
        tool_call_ids: list[str],
    ) -> list[dict[str, Any]]:
        """Process tool results that follow an assistant message with tool calls."""
        # Look ahead in the messages for tool results
        for j in range(assistant_msg_index + 1, len(finalized_prompt.finalized_messages)):
            next_msg = finalized_prompt.finalized_messages[j]
            # Only process user messages that might have tool results
            if not isinstance(next_msg, PromptUserMessage):
                continue

            # Check each content item for tool results
            for content_item in next_msg.content:
                if (
                    isinstance(content_item, PromptToolResultContent)
                    and content_item.tool_call_id in tool_call_ids
                ):
                    tool_message = self._create_tool_result_message(content_item)
                    messages.append(tool_message)

        return messages

    def _create_tool_result_message(self, content_item: PromptToolResultContent) -> dict[str, Any]:
        """Create a tool result message from a PromptToolResultContent item."""
        tool_result_content = []
        for result_item in content_item.content:
            if isinstance(result_item, PromptTextContent):
                tool_result_content.append(result_item.text)

        tool_content = "\n".join(tool_result_content) if tool_result_content else ""

        # Create tool message
        tool_message = {
            "role": "tool",
            "tool_call_id": content_item.tool_call_id,
            "content": tool_content,
        }

        # Only add name if it's not None
        if content_item.tool_name:
            tool_message["name"] = content_item.tool_name

        return tool_message
