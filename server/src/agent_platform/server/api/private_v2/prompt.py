import json
from typing import Literal

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
from structlog import get_logger

from agent_platform.core.context import AgentServerContext
from agent_platform.core.model_selector.default import DefaultModelSelector
from agent_platform.core.model_selector.selection_request import ModelSelectionRequest
from agent_platform.core.platforms.base import PlatformClient, PlatformParameters
from agent_platform.core.prompts import Prompt
from agent_platform.core.responses import ResponseMessage
from agent_platform.server.api.private_v2.utils import create_minimal_kernel
from agent_platform.server.auth import AuthedUser

router = APIRouter()
logger = get_logger(__name__)

ModelType = Literal[
    "llm", "embedding", "text-to-image", "text-to-audio", "audio-to-text"
]


def _create_platform_client_and_get_model(
    request: Request,
    user: AuthedUser,
    platform_config_raw: dict,
    model: str | None = None,
    model_type: ModelType = "llm",
):
    platform_config = PlatformParameters.model_validate(platform_config_raw)

    ctx = AgentServerContext.from_request(
        request=request,
        user=user,
        version=None,
    )

    # Pass the context to create_minimal_kernel
    kernel = create_minimal_kernel(ctx)
    platform_client = PlatformClient.from_platform_config(
        kernel=kernel,
        config=platform_config,
    )

    # Attach the platform client to the kernel
    platform_client.attach_kernel(kernel)

    # Test the platform client
    model_selector = DefaultModelSelector()
    model = model_selector.select_model(
        platform=platform_client,
        request=ModelSelectionRequest(
            model_type=model_type,
            direct_model_name=model,
        ),
    )

    return platform_client, model


@router.post("/generate", response_model=ResponseMessage)
async def prompt_generate(  # noqa: PLR0913
    prompt: Prompt,
    # Why no strong type? Discriminated union via our dataclasses + FastAPI
    # was giving us some issues here; quick fix to keep moving for now.
    platform_config_raw: dict,
    user: AuthedUser,
    request: Request,
    model: str | None = None,
    model_type: ModelType = "llm",
):
    await prompt.finalize_messages()

    platform_client, model = _create_platform_client_and_get_model(
        request=request,
        user=user,
        platform_config_raw=platform_config_raw,
        model=model,
        model_type=model_type,
    )

    platform_specific_prompt = await platform_client.converters.convert_prompt(
        prompt,
        model_id=model,
    )

    response = await platform_client.generate_response(
        prompt=platform_specific_prompt,
        model=model,
    )

    return response.excluding_raw_response()


@router.post("/stream")
async def prompt_stream(  # noqa: PLR0913
    prompt: Prompt,
    platform_config_raw: dict,
    user: AuthedUser,
    request: Request,
    model: str | None = None,
    model_type: ModelType = "llm",
) -> EventSourceResponse:
    await prompt.finalize_messages()

    platform_client, model = _create_platform_client_and_get_model(
        request=request,
        user=user,
        platform_config_raw=platform_config_raw,
        model=model,
        model_type=model_type,
    )

    platform_specific_prompt = await platform_client.converters.convert_prompt(
        prompt,
        model_id=model,
    )

    async def event_generator():
        async for delta in platform_client.generate_stream_response(
            prompt=platform_specific_prompt,
            model=model,
        ):
            # Ignore raw response, clients likely don't care and it varies
            # by platform
            if delta.path == "/raw_response":
                continue

            yield {"data": json.dumps(delta.model_dump())}

    return EventSourceResponse(event_generator())
