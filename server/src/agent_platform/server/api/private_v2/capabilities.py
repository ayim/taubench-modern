import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request
from structlog import get_logger

from agent_platform.core.context import AgentServerContext
from agent_platform.core.delta.combine_delta import combine_generic_deltas
from agent_platform.core.errors import PlatformError
from agent_platform.core.mcp import MCPServer
from agent_platform.core.model_selector import DefaultModelSelector
from agent_platform.core.model_selector.selection_request import ModelSelectionRequest
from agent_platform.core.platforms import (
    AnyPlatformParameters,
    PlatformClient,
)
from agent_platform.core.platforms.base import PlatformParameters
from agent_platform.core.prompts import (
    Prompt,
    PromptTextContent,
    PromptUserMessage,
)
from agent_platform.core.responses import (
    ResponseMessage,
    ResponseToolUseContent,
)
from agent_platform.core.tools import ToolDefinition
from agent_platform.server.agent_architectures import AgentArchManager
from agent_platform.server.api.private_v2.utils import create_minimal_kernel
from agent_platform.server.auth.handlers import AuthedUser
from agent_platform.server.kernel.tools import AgentServerToolsInterface
from agent_platform.server.kernel.tools_caching import ToolDefinitionCache

router = APIRouter()
logger = get_logger(__name__)


@dataclass
class _Book:
    title: Annotated[str, "The title of the book"]
    author: Annotated[str, "The author's name"]
    # Showing example of using field(metadata={"description": ...})
    year: int = field(metadata={"description": "Year the book was published"})
    # We tell the model to "completely omit" optional fields; the reasoning
    # models I've tested were confused that nothing was optional causing
    # increased latency on the /test endpoint... lol
    category: Annotated[str | None, "The category of the book"] = None


@dataclass
class ListMCPToolsRequest:
    """Payload schema for listing tools from MCP servers."""

    mcp_servers: list[MCPServer] = field(metadata={"description": "The MCP servers to query for tools."})


def _basic_test_prompt_with_tool() -> tuple[Prompt, Callable[[ResponseMessage], bool]]:
    async def _add_book(book: Annotated[_Book, "The book to add to the database"]):
        """Store a new book in the database."""
        return {"status": "success", "title": book.title}

    def _validate_response(response: ResponseMessage) -> bool:
        for content in response.content:
            if isinstance(content, ResponseToolUseContent):
                # Loosen this to just check that we called the tool
                return content.tool_name == "_add_book"

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
        # To prepare for reasoning models, we need to allow
        # for more output tokens (no longer just the response, but
        # also any "reasoning" happening behind the scenes)
        max_output_tokens=4096,
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

    platform_errors = []

    try:
        start_time = time.time()
        regular_response = await platform_client.generate_response(
            prompt=platform_prompt,
            model=model,
        )
        generation_latency = f"{(time.time() - start_time) * 1000:.2f}ms"
        regular_valid = validate_response(regular_response)
    except PlatformError as pex:
        platform_errors.append(pex.to_log_context())
        logger.exception(
            "Failed to validate regular response",
            error=pex,
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
    except PlatformError as pex:
        platform_errors.append(pex.to_log_context())
        logger.exception(
            "Failed to validate streaming response",
            error=pex,
        )

    results = {}
    results[name] = {
        "ok": regular_valid and streaming_valid,
        "generate": {
            "ok": regular_valid,
            "latencyMs": generation_latency,
        },
        "stream": {
            "ok": streaming_valid,
            "latencyMs": streaming_latency,
        },
        "errors": platform_errors,
    }

    return results


@router.get("/architectures")
async def get_architectures(
    user: AuthedUser,
):
    agent_arch_manager = AgentArchManager(
        wheels_path="./todo-for-out-of-process/wheels",
        websocket_addr="todo://think-about-out-of-process",
    )

    return agent_arch_manager.get_architectures()


@router.get("/platforms")
async def get_platforms(
    user: AuthedUser,
    response_model=dict,  # The response is a JSON schema dictionary
    summary="Get OpenAPI Schema for Platform Parameters",
):
    """
    This endpoint returns detailed information about all supported model platforms
    and their configuration parameters, including field descriptions, types,
    and whether they are required or optional.

    The schema returned represents a union of all possible platform parameter
    types.
    """
    from pydantic import TypeAdapter

    schema = {}
    try:
        # Create a TypeAdapter for the Union type
        adapter = TypeAdapter(AnyPlatformParameters)

        # Generate the single JSON schema for the Union type
        schema = adapter.json_schema()
    except Exception as ex:
        logger.exception("Failed to generate platform parameters schema", error=ex)
        raise HTTPException(
            status_code=500,
            detail="Failed to generate platform parameters schema",
        ) from ex

    return schema


@router.post("/platforms/{kind}/test")
async def test_model_platform_params(
    user: AuthedUser,
    kind: str,
    platform_params: dict,
    request: Request,
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
            # Create a context from the mock request and user
            ctx = AgentServerContext.from_request(
                request=request,
                user=user,
                version=None,
            )

            # Pass the context to create_minimal_kernel
            kernel = create_minimal_kernel(ctx)
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
                ),
            )

            testing_tasks = []
            for name, (prompt, validate_response) in [
                # Let's just run the tool test, as it supercedes the basic test
                # (if we can't run a tool, we likely can't generate basic responses either)
                ("simple_tool", _basic_test_prompt_with_tool()),
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
                "kind": parsed_params.kind,
                "selected_model": model,
            }
            for result in results:
                combined_results.update(result)

            # Return the combined results
            return combined_results
        except Exception as ex:
            raise HTTPException(
                status_code=400,
                detail=("Failed to create a platform client with the provided parameters"),
            ) from ex
    except Exception as ex:
        raise HTTPException(
            status_code=400,
            detail="Invalid platform parameters",
        ) from ex


@router.post("/mcp/tools")
async def list_mcp_tools(
    user: AuthedUser,
    payload: ListMCPToolsRequest,
    request: Request,
) -> dict:
    """List tools available from the provided MCP servers.

    Returns a mapping of each server to the tools discovered for that server.
    """
    context = AgentServerContext.from_request(
        request=request,
        user=user,
    )
    kernel = create_minimal_kernel(context)

    iface = AgentServerToolsInterface()
    # Recent changes to how headers are passed require this method
    # to have a minimal kernel, else tool listing will fail
    iface.attach_kernel(kernel)

    async def _per_server(server: MCPServer):
        # Create task first, then wait with timeout to avoid cancel scope issues
        timeout = 30.0
        task = asyncio.create_task(iface.from_mcp_servers([server]))

        try:
            mcp_result = await asyncio.wait_for(task, timeout=timeout)
            tools = mcp_result.tools
            issues = mcp_result.issues
        except TimeoutError:
            logger.warning(f"Timed out listing tools from MCP server {server.url}")
            # Cancel the task gracefully
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass  # Expected when we cancel
                except Exception:
                    pass  # Suppress any cleanup errors
            return {
                "server": server.model_dump(),
                "tools": [],
                "issues": [f"Failed to list tools: timeout after {timeout} seconds"],
            }
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception(f"Failed to list tools from MCP server {server.url} ({exc!s})")
            return {
                "server": server.model_dump(),
                "tools": [],
                "issues": [f"Failed to list tools: {exc!s}"],
            }

        return {
            "server": server.model_dump(),
            "tools": [t.model_dump() for t in tools],
            "issues": issues,
        }

    ToolDefinitionCache().clear_specific_urls_or_keys(
        [server.cache_key for server in payload.mcp_servers if server.cache_key]
    )
    results = await asyncio.gather(*[_per_server(srv) for srv in payload.mcp_servers])
    return {"results": results}
