from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from agent_platform.core.kernel import Kernel
from agent_platform.core.kernel_interfaces.model_platform import PlatformInterface
from agent_platform.core.platforms.base import PlatformClient
from agent_platform.core.prompts import Prompt
from agent_platform.core.responses import ResponseMessage
from agent_platform.core.responses.streaming import ResponseStreamPipe
from agent_platform.server.kernel.kernel_mixin import UsesKernelMixin


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
        with self.kernel.otel.span("generate_response") as span:
            span.add_event("finalizing prompt")
            finalized_prompt = await prompt.finalize_messages(self.kernel)
            span.add_event_with_artifacts(
                "finalized prompt",
                ("prompt-finalized.yaml", prompt.to_pretty_yaml()),
            )
            converted_prompt = await self._internal_client.converters.convert_prompt(
                finalized_prompt,
                model_id=model,
            )

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
        with self.kernel.otel.span("stream_response") as span:
            span.add_event("finalizing prompt")
            finalized_prompt = await prompt.finalize_messages(self.kernel)
            span.add_event_with_artifacts(
                "finalized prompt",
                ("prompt-finalized.yaml", prompt.to_pretty_yaml()),
            )

            converted_prompt = await self._internal_client.converters.convert_prompt(
                finalized_prompt,
                model_id=model,
            )

            response_stream = self._internal_client.generate_stream_response(
                converted_prompt,
                model,
            )
            # Why include the prompt? Some information (like tool defs) is not
            # included in the response stream, so we need to include the prompt
            # to get at that information.
            stream_pipe = ResponseStreamPipe(response_stream, finalized_prompt)

            try:
                yield stream_pipe
            finally:
                if stream_pipe.reassembled_response:
                    span.add_event_with_artifacts(
                        "stream closed",
                        (
                            "response-reassembled.json",
                            stream_pipe.reassembled_response.model_dump_json(indent=2),
                        ),
                    )
                await stream_pipe.aclose()
                span.add_event("stream closed")

