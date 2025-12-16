"""Shared prompts generation service.

This module provides the core business logic for prompt generation that can be
shared between the HTTP endpoint and DirectKernelTransport.
"""

import json

# Import for type conversion
from sema4ai_docint.agent_server_client.transport.base import (
    ResponseMessage as TransportResponseMessage,
)

from agent_platform.core.agent import Agent
from agent_platform.core.context import AgentServerContext
from agent_platform.core.model_selector.default import DefaultModelSelector
from agent_platform.core.model_selector.selection_request import ModelSelectionRequest
from agent_platform.core.platforms.base import PlatformClient, PlatformParameters
from agent_platform.core.platforms.configs import ModelType
from agent_platform.core.prompts import Prompt
from agent_platform.core.responses import ResponseMessage as CoreResponseMessage
from agent_platform.server.api.private_v2.utils import create_minimal_kernel
from agent_platform.server.kernel.model_platform import AgentServerPlatformInterface


def create_platform_interface_and_get_model(
    platform_config_raw: dict,
    context: AgentServerContext,
    model: str | None = None,
    model_type: ModelType = "llm",
):
    """Create platform interface and select model.

    Args:
        platform_config_raw: The platform configuration dictionary
        context: The agent server context
        model: Optional specific model to use
        model_type: Type of model (default: "llm")

    Returns:
        tuple of (platform_interface, selected_model)
    """
    platform_config = PlatformParameters.model_validate(platform_config_raw)

    # Pass the context to create_minimal_kernel
    kernel = create_minimal_kernel(context)
    platform_client = PlatformClient.from_platform_config(
        kernel=kernel,
        config=platform_config,
    )

    # Attach the platform client to the kernel
    platform_client.attach_kernel(kernel)

    # Create the platform interface with proper tracing capabilities
    platform_interface = AgentServerPlatformInterface(platform_client)
    platform_interface.attach_kernel(kernel)

    # Select model using model selector
    model_selector = DefaultModelSelector()
    selected_model = model_selector.select_model(
        platform=platform_client,
        request=ModelSelectionRequest(
            model_type=model_type,
            direct_model_name=model,
        ),
    )

    return platform_interface, selected_model


async def generate_prompt_response(
    prompt: Prompt,
    platform_config_raw: dict,
    server_context: AgentServerContext,
    model: str | None = None,
    model_type: ModelType = "llm",
    agent_id: str | None = None,
    agent: Agent | None = None,
    thread_id: str | None = None,
) -> CoreResponseMessage:
    """Generate a response to a prompt using the platform interface.

    This is the core business logic extracted from the prompts/generate endpoint
    that can be reused by both the HTTP API and DirectKernelTransport.

    Args:
        prompt: The prompt to generate a response for
        platform_config_raw: The platform configuration dictionary
        server_context: The agent server context for tracing and observability
        model: Optional specific model to use
        model_type: Type of model (default: "llm")
        agent_id: Optional agent ID for metadata
        agent: Optional agent object for metadata
        thread_id: Optional thread ID for metadata

    Returns:
        CoreResponseMessage: The generated response (core type)

    Raises:
        ValueError: If platform configuration is invalid
        RuntimeError: If prompt generation fails
    """
    with server_context.start_span("prompt_generate") as span:
        # Set LangSmith metadata attributes similar to sync_run
        if agent_id:
            span.set_attribute("langsmith.metadata.agent_id", str(agent_id))
        if agent:
            span.set_attribute("langsmith.metadata.agent_name", agent.name)
        if thread_id:
            span.set_attribute("langsmith.metadata.thread_id", str(thread_id))
        span.set_attribute(
            "langsmith.metadata.user_id",
            server_context.user_context.user.cr_user_id
            if server_context.user_context.user.cr_user_id
            else server_context.user_context.user.sub,
        )
        span.set_attribute("langsmith.metadata.model_type", model_type)
        if model:
            span.set_attribute("langsmith.metadata.model", model)

        with server_context.start_span("configure_platform") as platform_span:
            platform_span.set_attribute(
                "input.value",
                json.dumps(
                    {
                        "model": model,
                        "model_type": model_type,
                    }
                ),
            )

            platform_interface, selected_model = create_platform_interface_and_get_model(
                platform_config_raw=platform_config_raw,
                context=server_context,
                model=model,
                model_type=model_type,
            )

            platform_span.set_attribute(
                "output.value",
                json.dumps(
                    {
                        "selected_model": selected_model,
                    }
                ),
            )

        # Generate response
        response = await platform_interface.generate_response(
            prompt=prompt,
            model=selected_model,
        )

        # Update span name with model info
        span.update_name(f"prompt_generate[{selected_model}]")

        return response


def convert_core_response_to_transport(
    response: CoreResponseMessage,
) -> TransportResponseMessage:
    """Convert core ResponseMessage to transport ResponseMessage.

    The core ResponseMessage (dataclass) and transport ResponseMessage (Pydantic)
    have slightly different structures. This function converts between them.

    Args:
        response: Core ResponseMessage from platform

    Returns:
        TransportResponseMessage: Transport-compatible response
    """
    # Convert content items to dicts
    content_dicts = [item.model_dump() for item in response.content]

    return TransportResponseMessage(
        content=content_dicts,
        role=response.role,
        raw_response=None,  # Exclude raw_response for transport
        stop_reason=response.stop_reason,
        usage=response.usage.model_dump() if response.usage else {},
        metrics=response.metrics,
        metadata=response.metadata,
        additional_response_fields=response.additional_response_fields,
    )
