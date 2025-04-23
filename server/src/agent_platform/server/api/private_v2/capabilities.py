from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Annotated

from fastapi import APIRouter, HTTPException
from structlog import get_logger

from agent_platform.core.agent import Agent, AgentArchitecture
from agent_platform.core.delta.combine_delta import combine_generic_deltas
from agent_platform.core.model_selector import DefaultModelSelector
from agent_platform.core.model_selector.selection_request import ModelSelectionRequest
from agent_platform.core.platforms.azure import AzureOpenAIPlatformParameters
from agent_platform.core.platforms.base import PlatformClient, PlatformParameters
from agent_platform.core.platforms.bedrock import BedrockPlatformParameters
from agent_platform.core.platforms.cortex import CortexPlatformParameters
from agent_platform.core.platforms.openai import OpenAIPlatformParameters
from agent_platform.core.prompts import (
    Prompt,
    PromptTextContent,
    PromptUserMessage,
)
from agent_platform.core.responses import (
    ResponseMessage,
    ResponseTextContent,
    ResponseToolUseContent,
)
from agent_platform.core.runbook import Runbook
from agent_platform.core.runs import Run
from agent_platform.core.thread import Thread
from agent_platform.core.tools import ToolDefinition
from agent_platform.core.user import User
from agent_platform.server.agent_architectures import AgentArchManager
from agent_platform.server.auth.handlers import AuthedUser
from agent_platform.server.kernel import AgentServerKernel

router = APIRouter()
logger = get_logger(__name__)


@dataclass
class _Book:
    title: Annotated[str, "The title of the book"]
    author: Annotated[str, "The author's name"]
    category: Annotated[str | None, "The category of the book"]
    # Showing example of using field(metadata={"description": ...})
    year: int = field(metadata={"description": "Year the book was published"})


def _create_minimal_kernel(user: User) -> AgentServerKernel:
    empty_agent = Agent(
        user_id=user.user_id,
        version="0.0.0",
        name="empty-agent",
        description="empty-agent",
        agent_architecture=AgentArchitecture(name="", version=""),
        platform_configs=[],
        runbook_structured=Runbook(content=[], raw_text=""),
    )
    empty_thread = Thread(
        user_id=user.user_id,
        agent_id=empty_agent.agent_id,
        name="empty-thread",
        messages=[],
    )
    empty_run = Run(
        run_id="00000000-0000-0000-0000-000000000000",
        agent_id=empty_agent.agent_id,
        thread_id=empty_thread.thread_id,
    )
    return AgentServerKernel(
        user=user,
        thread=empty_thread,
        agent=empty_agent,
        run=empty_run,
    )


def _basic_test_prompt() -> tuple[Prompt, Callable[[ResponseMessage], bool]]:
    content = PromptTextContent(
        text="This is a system test, please reply with the string 'avacado'",
    )

    def _validate_response(response: ResponseMessage) -> bool:
        for content in response.content:
            if isinstance(content, ResponseTextContent):
                return "avacado" in content.text.lower()
        return False

    return Prompt(
        messages=[
            PromptUserMessage(content=[content]),
        ],
    ), _validate_response


def _basic_test_prompt_with_tool() -> tuple[Prompt, Callable[[ResponseMessage], bool]]:
    async def _add_book(book: Annotated[_Book, "The book to add to the database"]):
        """Store a new book in the database."""
        return {"status": "success", "title": book.title}

    def _validate_response(response: ResponseMessage) -> bool:
        for content in response.content:
            if isinstance(content, ResponseToolUseContent):
                return (
                    content.tool_name == "_add_book"
                    and "book" in content.tool_input
                    and "title" in content.tool_input["book"]
                    and content.tool_input["book"]["title"].lower() == "foundation"
                )

        return False

    content = PromptTextContent(
        """
        This is an end-to-end test, please call the tool
        called add_book with the following book:

        Title: "Foundation"
        Author: "Isaac Asimov"
        Year: 1951

        Emit nothing else but the tool call with the
        book information _exactly_ as shown above. Completely
        omit any optional fields.
        """,
    )

    return Prompt(
        system_instruction=(
            """
            You are an expert librarian. You are given a book
            and you need to add it to the database. If any
            information is missing/optional, you should leave
            it out instead of trying to guess it!! Do NOT even
            include an empty string/null for optional fields, completely
            omit them.
            """
        ),
        messages=[PromptUserMessage(content=[content])],
        tools=[ToolDefinition.from_callable(_add_book)],
        temperature=0.0,
        max_output_tokens=512,
    ), _validate_response


async def _run_test(
    name: str,
    platform_client: PlatformClient,
    prompt: Prompt,
    model: str,
    validate_response: Callable[[ResponseMessage], bool],
):
    """
    Run a test of the platform client with the given prompt and model in
    both non-streaming and streaming modes.

    Returns a dictionary with the results of the two tests.
    """
    import time

    regular_valid = False
    streaming_valid = False
    generation_latency = None
    streaming_latency = None

    await prompt.finalize_messages()
    platform_prompt = await platform_client.converters.convert_prompt(
        prompt,
        model_id=model,
    )

    try:
        start_time = time.time()
        regular_response = await platform_client.generate_response(
            prompt=platform_prompt,
            model=model,
        )
        generation_latency = f"{(time.time() - start_time) * 1000:.2f}ms"
        regular_valid = validate_response(regular_response)
    except Exception as ex:
        logger.exception(
            "Failed to validate regular response",
            error=ex,
        )

    try:
        start_time = time.time()
        deltas = []
        async for delta in platform_client.generate_stream_response(
            prompt=platform_prompt,
            model=model,
        ):
            deltas.append(delta)

        streaming_response = ResponseMessage.model_validate(
            combine_generic_deltas(deltas),
        )
        streaming_latency = f"{(time.time() - start_time) * 1000:.2f}ms"
        streaming_valid = validate_response(streaming_response)
    except Exception as ex:
        logger.exception(
            "Failed to validate streaming response",
            error=ex,
        )

    results = {}
    results[name] = {
        "non-streaming-succeeded": regular_valid,
        "streaming-succeeded": streaming_valid,
        "non-streaming-latency-ms": generation_latency,
        "streaming-latency-ms": streaming_latency,
    }

    return results


def _get_friendly_type_name(type_annotation):  # noqa: PLR0911
    """Convert a type annotation to a friendly string representation."""
    if type_annotation is str:
        return "str"
    elif type_annotation is int:
        return "int"
    elif type_annotation is bool:
        return "bool"
    elif type_annotation is float:
        return "float"
    elif type_annotation is dict:
        return "dict"
    elif type_annotation is list:
        return "list"
    elif hasattr(type_annotation, "__name__"):
        return type_annotation.__name__
    else:
        # Fall back to the str representation but clean it up
        type_str = str(type_annotation)
        # Remove angle brackets and class prefix
        type_str = type_str.replace("<class '", "").replace("'>", "")
        # Keep just the class name without module path
        if "." in type_str:
            return type_str.split(".")[-1]
        return type_str


@router.get("/architectures")
async def get_architectures(
    user: AuthedUser,
):
    agent_arch_manager = AgentArchManager(
        wheels_path="./todo-for-out-of-process/wheels",
        websocket_addr="todo://think-about-out-of-process",
    )

    return agent_arch_manager.get_architectures()


@router.get("/providers")
async def get_providers(
    user: AuthedUser,
):
    """
    This endpoint returns detailed information about all supported model platforms
    and their configuration parameters, including field descriptions, types,
    and whether they are required or optional.
    """
    from dataclasses import fields
    from typing import get_args, get_origin, get_type_hints

    # NOTE: This is the key place where we define what the platforms we support; if your
    # platform is not in this list, it will not be shown in the UI!!
    platform_parameters = [
        AzureOpenAIPlatformParameters,
        OpenAIPlatformParameters,
        BedrockPlatformParameters,
        CortexPlatformParameters,
    ]

    result = []
    for param_class in platform_parameters:
        param_info = {
            "kind": param_class.__name__,
            "description": param_class.__doc__.strip() if param_class.__doc__ else None,
            "fields": [],
        }

        # Get type hints to handle complex types
        type_hints = get_type_hints(param_class)

        for field_obj in fields(param_class):
            # Skip fields that aren't meant to be initialized directly
            if not field_obj.init or field_obj.name.startswith("_"):
                continue

            # Determine field type information
            field_type = type_hints.get(field_obj.name)

            # Handle Union types (like str | None)
            is_optional = False
            if get_origin(field_type) is not None:
                args = get_args(field_type)
                # Check if None is one of the union options
                if type(None) in args:
                    is_optional = True
                type_str = " | ".join(
                    _get_friendly_type_name(arg)
                    for arg in args
                    if arg is not type(None)
                )
            else:
                type_str = _get_friendly_type_name(field_type)

            # A field is also optional if it has a default value
            if field_obj.default is not None or field_obj.default_factory is not None:
                is_optional = True

            # Get field metadata
            metadata = field_obj.metadata or {}
            description = metadata.get("description", "")
            example = metadata.get("example", None)

            field_info = {
                "name": field_obj.name,
                "type": type_str,
                "required": not is_optional,
                "description": description,
            }

            if example is not None:
                field_info["example"] = example

            param_info["fields"].append(field_info)

        result.append(param_info)

    return result


@router.post("/providers/{kind}/test")
async def test_model_platform_params(
    user: AuthedUser,
    kind: str,
    platform_params: dict,
):
    """
    This endpoint is used to test platform parameters by making a series
    of basic requests to the platform.

    The endpoint returns a dictionary with the results of the tests.
    """
    from asyncio import create_task, gather

    # Set kind from route
    platform_params["kind"] = kind

    try:
        parsed_params = PlatformParameters.model_validate(platform_params)
        try:
            kernel = _create_minimal_kernel(user)
            platform_client = PlatformClient.from_platform_config(
                kernel=kernel,
                config=parsed_params,
            )

            # Attach the platform client to the kernel
            platform_client.attach_kernel(kernel)

            # Test the platform client
            model_selector = DefaultModelSelector()
            model = model_selector.select_model(
                platform=platform_client,
                request=ModelSelectionRequest(
                    model_type="llm",
                    quality_tier="balanced",
                ),
            )

            testing_tasks = []
            for name, (prompt, validate_response) in [
                ("basic-test", _basic_test_prompt()),
                ("basic-test-with-tool", _basic_test_prompt_with_tool()),
            ]:
                testing_tasks.append(
                    create_task(
                        _run_test(
                            name=name,
                            platform_client=platform_client,
                            prompt=prompt,
                            model=model,
                            validate_response=validate_response,
                        ),
                    ),
                )

            # Run the tests in parallel
            results = await gather(*testing_tasks)

            # Combine the results into a single dictionary
            combined_results = {
                "platform-kind": parsed_params.kind,
            }
            for result in results:
                combined_results.update(result)

            # Return the combined results
            return combined_results
        except Exception as ex:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Failed to create a platform client with the provided parameters"
                ),
            ) from ex
    except Exception as ex:
        raise HTTPException(
            status_code=400,
            detail="Invalid platform parameters",
        ) from ex
