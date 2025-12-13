import json
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from sse_starlette.sse import EventSourceResponse
from structlog import get_logger

from agent_platform.core.agent import Agent
from agent_platform.core.agent.observability_config import ObservabilityConfig
from agent_platform.core.context import AgentServerContext
from agent_platform.core.model_selector.default import DefaultModelSelector
from agent_platform.core.model_selector.selection_request import ModelSelectionRequest
from agent_platform.core.platforms.base import PlatformClient, PlatformParameters
from agent_platform.core.prompts import Prompt
from agent_platform.core.responses import ResponseMessage
from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.api.private_v2.utils import create_minimal_kernel
from agent_platform.server.auth import AuthedUser
from agent_platform.server.kernel.model_platform import AgentServerPlatformInterface

router = APIRouter()
logger = get_logger(__name__)

ModelType = Literal["llm", "embedding", "text-to-image", "text-to-audio", "audio-to-text"]


async def _get_agent_and_observability_config(
    storage: StorageDependency,
    user: AuthedUser,
    platform_config_raw: dict | None,
    agent_id: str | None,
    thread_id: str | None,
) -> tuple[Agent | None, ObservabilityConfig | None, dict]:
    """
    Get agent and observability config if agent_id is available.

    Returns:
        tuple of (agent, observability_config, platform_config_raw)
    """
    agent = None
    observability_config = None

    if platform_config_raw is None:
        if thread_id:
            thread = await storage.get_thread(user.user_id, thread_id)
            agent_id = thread.agent_id
        if agent_id is not None:
            agent = await storage.get_agent(user.user_id, agent_id)
            if not agent.platform_configs:
                raise HTTPException(status_code=400, detail="Agent has no platform configs")
            platform_config_raw = agent.platform_configs[0].model_dump()
        else:
            raise HTTPException(status_code=400, detail="platform_config or agent_id required")
    elif agent_id is not None:
        # Even if platform_config_raw is provided, get agent for observability config
        agent = await storage.get_agent(user.user_id, agent_id)

    # Fetch the first LangSmith observability config from agent if available
    if agent:
        for config in agent.observability_configs:
            if config.type == "langsmith":
                observability_config = config
                break

    if observability_config is None:
        logger.info("No LangSmith observability config found, using default")

    return agent, observability_config, platform_config_raw


def _create_platform_interface_and_get_model(
    platform_config_raw: dict,
    context: AgentServerContext,
    model: str | None = None,
    model_type: ModelType = "llm",
):
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

    # Test the platform client
    model_selector = DefaultModelSelector()
    model = model_selector.select_model(
        platform=platform_client,
        request=ModelSelectionRequest(
            model_type=model_type,
            direct_model_name=model,
        ),
    )

    return platform_interface, model


@router.post("/generate", response_model=ResponseMessage)
async def prompt_generate(
    prompt: Prompt,
    user: AuthedUser,
    request: Request,
    storage: StorageDependency,
    # Why no strong type? Discriminated union via our dataclasses + FastAPI
    # was giving us some issues here; quick fix to keep moving for now.
    platform_config_raw: dict | None = None,
    model: str | None = None,
    model_type: ModelType = "llm",
    agent_id: str | None = None,
    thread_id: str | None = None,
    minimize_reasoning: bool = False,
):
    prompt.minimize_reasoning = minimize_reasoning
    await prompt.finalize_messages()

    # Get agent and observability config if agent_id is available
    agent, observability_config, platform_config_raw = await _get_agent_and_observability_config(
        storage=storage,
        user=user,
        platform_config_raw=platform_config_raw,
        agent_id=agent_id,
        thread_id=thread_id,
    )

    # Create agent server context with observability config
    server_context = AgentServerContext.from_request(
        request=request,
        user=user,
        version="2.0.0",
        observability_config=observability_config,
        agent_id=agent_id,
    )

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

            platform_interface, model = _create_platform_interface_and_get_model(
                platform_config_raw=platform_config_raw,
                context=server_context,
                model=model,
                model_type=model_type,
            )

            platform_span.set_attribute(
                "output.value",
                json.dumps(
                    {
                        "selected_model": model,
                    }
                ),
            )

        response = await platform_interface.generate_response(
            prompt=prompt,  # Use original prompt, not platform_specific_prompt
            model=model,
        )

        # Update span name with model info
        span.update_name(f"prompt_generate[{model}]")

        return response.excluding_raw_response()


@router.post("/stream")
async def prompt_stream(
    prompt: Prompt,
    user: AuthedUser,
    request: Request,
    storage: StorageDependency,
    platform_config_raw: dict | None = None,
    model: str | None = None,
    model_type: ModelType = "llm",
    agent_id: str | None = None,
    thread_id: str | None = None,
    minimize_reasoning: bool = False,
) -> EventSourceResponse:
    prompt.minimize_reasoning = minimize_reasoning
    await prompt.finalize_messages()

    # Get agent and observability config if agent_id is available
    agent, observability_config, platform_config_raw = await _get_agent_and_observability_config(
        storage=storage,
        user=user,
        platform_config_raw=platform_config_raw,
        agent_id=agent_id,
        thread_id=thread_id,
    )

    # Create agent server context with observability config
    server_context = AgentServerContext.from_request(
        request=request,
        user=user,
        version="2.0.0",
        observability_config=observability_config,
        agent_id=agent_id,
    )

    with server_context.start_span("prompt_stream") as span:
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

            platform_interface, model = _create_platform_interface_and_get_model(
                platform_config_raw=platform_config_raw,
                context=server_context,
                model=model,
                model_type=model_type,
            )

            platform_span.set_attribute(
                "output.value",
                json.dumps(
                    {
                        "selected_model": model,
                    }
                ),
            )

        # Update span name with model info
        span.update_name(f"prompt_stream[{model}]")

        async def event_generator():
            delta_count = 0
            with server_context.start_span("generate_stream_response") as stream_span:
                stream_span.set_attribute(
                    "input.value",
                    json.dumps(
                        {
                            "model": model,
                            "prompt_length": len(str(prompt)),
                        }
                    ),
                )

                # Use raw stream directly - no conversion overhead!
                async for delta in platform_interface.stream_raw_response(
                    prompt=prompt,
                    model=model,
                ):
                    # Ignore raw response, clients likely don't care and it varies
                    # by platform
                    if delta.path == "/raw_response":
                        continue

                    delta_count += 1
                    yield {"data": json.dumps(delta.model_dump())}

                # Set final stream metadata
                stream_span.set_attribute(
                    "output.value",
                    json.dumps(
                        {
                            "delta_count": str(delta_count),
                        }
                    ),
                )

        return EventSourceResponse(event_generator())
