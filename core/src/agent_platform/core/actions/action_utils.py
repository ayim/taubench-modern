import os
import random
import string
from collections.abc import Callable, Coroutine
from enum import IntEnum
from http import HTTPStatus
from typing import Any, TypedDict

from aiohttp import ClientSession
from jsonpointer import JsonPointer, JsonPointerException
from structlog import get_logger

from agent_platform.core.tools.tool_definition import ToolDefinition
from agent_platform.core.utils.url import safe_urljoin

logger = get_logger(__name__)


class ActionRunStatus(IntEnum):
    """Enum for action server run status codes."""

    NOT_RUN = 0  # Action has not been run yet
    PENDING = 1  # Action is pending/queued
    PASSED = 2  # Action completed successfully
    FAILED = 3  # Action failed
    CANCELLED = 4  # Action was cancelled


class ActionStatusResponse(TypedDict, total=False):
    """Response from action server status check."""

    status: int
    result: Any
    error_message: str


def _dereference_refs_recursive(item: Any, full_schema: dict) -> Any:
    """Recursively traverses a schema structure and
    resolves all $refs using jsonpointer."""
    if isinstance(item, dict):
        if "$ref" in item:
            # Found a reference, resolve it using jsonpointer
            ref_value = item["$ref"]
            pointer_path = ref_value
            try:
                # JSON Pointers in OpenAPI often omit the leading '#',
                # but jsonpointer expects a path starting with '/' or empty.
                # Assume internal reference if no scheme/authority present.
                if ref_value.startswith("#/"):
                    pointer_path = ref_value[1:]  # Remove '#'
                elif "/" in ref_value and ":" not in ref_value:  # Check for path vs URI
                    pointer_path = "/" + ref_value.lstrip("/")  # Ensure one leading '/'

                pointer = JsonPointer(pointer_path)
                resolved = pointer.resolve(full_schema)

                # Recursively dereference the resolved part itself
                return _dereference_refs_recursive(resolved, full_schema)
            except (
                JsonPointerException,
                ValueError,
                TypeError,
                KeyError,
                IndexError,
            ) as e:
                # Catch potential errors from jsonpointer or during path manipulation
                logger.warning(
                    f"Warning: Failed to resolve ref '{ref_value}' "
                    f"(path='{pointer_path}'): {e}. Skipping."
                )
                # Return the original item (with $ref) if resolution fails
                return item
        else:
            # No $ref, traverse deeper into dictionary values
            # Return a new dictionary with resolved values
            new_dict = {}
            for key, value in item.items():
                new_dict[key] = _dereference_refs_recursive(value, full_schema)
            return new_dict
    elif isinstance(item, list):
        # Traverse deeper into list items
        # Return a new list with resolved items
        new_list = []
        for value in item:
            new_list.append(_dereference_refs_recursive(value, full_schema))
        return new_list
    else:
        # Base case: non-dict, non-list items (string, number, boolean, null)
        return item


def _dereference_refs(spec: dict, full_schema: dict) -> dict:
    """
    Dereferences JSON schema $refs within the given spec dictionary,
    using the full_schema as the reference source.

    Handles nested references and returns a new dictionary with all
    references resolved. It assumes the input 'spec' should resolve
    to a dictionary structure.
    """
    # Start the recursive dereferencing process
    resolved_spec = _dereference_refs_recursive(spec, full_schema)

    # Ensure the final result is a dictionary, as expected by the caller context
    if not isinstance(resolved_spec, dict):
        # This might happen if the top-level 'spec' was just a $ref pointing
        # to a non-object schema (e.g., a string or array).
        raise TypeError(
            f"Dereferencing resulted in a non-dictionary type: {type(resolved_spec)}. "
            f"Input spec: {spec}"
        )
    return resolved_spec


async def _get_run_id_from_request_id(
    session: ClientSession,
    base_url: str,
    api_key: str,
    request_id: str,
) -> str | None:
    """Get the run ID from a request ID.

    Args:
        session: The aiohttp ClientSession to use
        base_url: The base URL of the action server
        api_key: The API key for authentication
        request_id: The request ID to get the run ID for

    Returns:
        The run ID if found, None otherwise
    """
    run_id_url = f"{base_url}/api/runs/run-id-from-request-id/{request_id}"
    try:
        async with session.get(
            run_id_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        ) as response:
            if response.status == HTTPStatus.OK:
                result = await response.json()
                run_id = result.get("run_id")
                if run_id:
                    logger.info(f"Found run ID {run_id} for request ID {request_id}")
                    return run_id
                else:
                    logger.warning(f"No run_id found in response for request ID {request_id}")
                    return None
            else:
                logger.warning(
                    f"Failed to get run ID for request ID {request_id}. Status: {response.status}"
                )
                return None
    except Exception as e:
        logger.error(f"Error getting run ID from request ID: {e!s}", exc_info=True)
        return None


async def _check_action_status(
    session: ClientSession | None,
    base_url: str,
    api_key: str,
    async_action_run_id: str,
    action_server_id: str,
) -> ActionStatusResponse:
    """Check the status of an action run.

    Args:
        session: Optional aiohttp ClientSession to reuse.
        If not provided, a new session will be created.
        base_url: The base URL of the action server (e.g., http://localhost:8080)
        api_key: The API key for authentication
        async_action_run_id: The ID of the async action run
        action_server_id: The ID of the action server

    Returns:
        dict: The response from the action server containing the run status
    """
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "x-action-server-pod-ip": action_server_id,
        }

        # If no session provided, create a new one
        should_close_session = False
        if session is None:
            session = ClientSession()
            should_close_session = True

        try:
            async with session.get(
                f"{base_url}/api/runs/{async_action_run_id}", headers=headers
            ) as response:
                if response.status != HTTPStatus.OK:
                    logger.warning(
                        f"Received invalid status code from action server: {response.status}"
                    )
                    return {"status": -1}  # Indicate error with status -1

                return await response.json()
        finally:
            # Only close the session if we created it
            if should_close_session:
                await session.close()
    except Exception as e:
        logger.error(f"Error checking action status: {e!s}", exc_info=True)
        return {"status": -1}


def _build_post_async_function(
    action_url: str,
    api_key: str,
    # Extra headers to be added to the request at
    # tool definition time
    additional_headers: dict | None = None,
) -> Callable[..., Coroutine[Any, Any, Any]]:
    async def _post_async_function(
        # Extra headers to be added to the request at
        # tool invocation time
        extra_headers: dict | None = None,
        **args: dict[str, Any],
    ) -> Any:
        import asyncio
        import uuid

        from aiohttp import ClientSession

        characters = string.ascii_letters + string.digits
        action_invocation_id = "".join(random.choice(characters) for _ in range(10))
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "x-action_invocation_id": action_invocation_id,
            **(additional_headers or {}),
            **(extra_headers or {}),
        }

        # Only add async headers if SEMA4AI_AGENT_SERVER_ENABLE_ASYNC_ACTION is true
        if os.getenv("SEMA4AI_AGENT_SERVER_ENABLE_ASYNC_ACTION", "").lower() == "true":
            headers.update(
                {
                    "x-actions-request-id": str(uuid.uuid4()),
                    "x-actions-async-timeout": str(
                        int(os.getenv("ACTIONS_ASYNC_TIMEOUT", "20"))
                    ),  # Default: 20 seconds timeout
                    "x-actions-async-callback": "",  # No callback URL
                }
            )

        # We can't have any headers that map to None, so filter them out
        safe_headers = {k: v for k, v in headers.items() if v is not None}

        async with ClientSession() as session:
            async with session.post(
                action_url,
                headers=safe_headers,
                json=args,
            ) as response:
                result = await response.json()

                # In case of async action, we need to poll for the status of the action
                # The action server will set the x-action-async-completion header to 1
                # if the action is async.
                # Ref: https://github.com/Sema4AI/actions/blob/master/action_server/docs/guides/16-run-action-sync-async.md
                is_async_action = response.headers.get("x-action-async-completion") == "1"
                async_action_run_id = response.headers.get("x-action-server-run-id")
                action_server_id = response.headers.get("x-action-server-pod-ip", "")
                if is_async_action:
                    # Extract base URL from the action URL
                    base_url = action_url.split("/api/actions/")[0]

                    # Start polling for action server status
                    # Default: 20 minutes with 10 second intervals
                    max_retries = int(os.getenv("ACTIONS_ASYNC_MAX_RETRIES", "120"))
                    # Default: 10 seconds between retries
                    retry_interval = float(os.getenv("ACTIONS_ASYNC_RETRY_INTERVAL", "10"))
                    retries = 0

                    while retries < max_retries:
                        try:
                            if async_action_run_id:
                                # Check action status
                                status_result = await _check_action_status(
                                    session=session,
                                    base_url=base_url,
                                    api_key=api_key,
                                    async_action_run_id=async_action_run_id,
                                    action_server_id=action_server_id,
                                )

                                status = status_result.get("status")

                                # Handle different status codes
                                if status == ActionRunStatus.PASSED:
                                    return {
                                        "error": status_result.get("error_message"),
                                        "result": status_result.get("result"),
                                    }
                                elif status == ActionRunStatus.FAILED:
                                    return {
                                        "error": status_result.get("error_message")
                                        or "Action failed",
                                        "result": None,
                                    }
                                elif status == ActionRunStatus.CANCELLED:
                                    return {"error": "Action was cancelled", "result": None}
                                else:
                                    logger.debug(f"Retrying action status check: {status}")

                            await asyncio.sleep(retry_interval)
                            retries += 1

                        except Exception as e:
                            logger.error(
                                f"Error checking async action status: {e!s}", exc_info=True
                            )
                            await asyncio.sleep(retry_interval)
                            retries += 1

                    # If we get here, we've timed out
                    logger.warning(f"Async action did not complete after {max_retries} retries")
                    return {"error": "Async action did not complete after timeout", "result": None}

                return result

    return _post_async_function


def _openapi_spec_to_tool_definitions(
    url: str,
    api_key: str,
    spec: dict,
    additional_headers: dict | None = None,
) -> list[ToolDefinition]:
    tool_definitions: list[ToolDefinition] = []

    for path, methods in spec.get("paths", {}).items():
        # Ignore, if not an actions path
        if not path.startswith("/api/actions"):
            continue

        for method, spec_with_ref in methods.items():
            # Ignore, if not a POST
            if method not in ["post"]:
                continue
            # Ignore, if it doesn't have a 200 response
            if "200" not in spec_with_ref.get("responses", {}):
                continue

            # Now, dereference the refs
            resolved_spec = _dereference_refs(spec_with_ref, full_schema=spec)

            # Get the action url
            action_url = safe_urljoin(url, path.lstrip("/"))

            # Get the requestBody's schema (JSON schema)
            request_body_schema = (
                resolved_spec.get("requestBody", {})
                .get("content", {})
                .get("application/json", {})
                .get("schema", {})
            )

            request_body_args = request_body_schema.get("properties", {})
            request_body_required = request_body_schema.get("required", [])

            # Start building the schema
            tool_definition = ToolDefinition(
                name=resolved_spec.get("operationId", ""),
                description=resolved_spec.get("description", ""),
                input_schema={
                    "type": "object",
                    # Instead of only extracting specific fields, preserve the entire schema
                    # This ensures we don't lose nested properties, anyOf, default, etc.
                    "properties": request_body_args,
                    "required": request_body_required,
                },
                category="action-tool",
                function=_build_post_async_function(
                    action_url=action_url,
                    api_key=api_key,
                    additional_headers=additional_headers,
                ),
            )

            # Now, reduce the spec to only the required information
            tool_definitions.append(tool_definition)

    return tool_definitions


async def get_spec_and_build_tool_definitions(
    url: str,
    api_key: str,
    allowed_actions: list[str],
    additional_headers: dict | None = None,
) -> list[ToolDefinition]:
    from aiohttp import ClientSession

    # Get the spec url
    if not url.startswith("http"):
        url = "http://" + url
    spec_url = safe_urljoin(url, "openapi.json")

    async with ClientSession() as session:
        async with session.get(spec_url) as response:
            spec = await response.json()

    definitions = _openapi_spec_to_tool_definitions(url, api_key, spec, additional_headers)
    if len(allowed_actions) > 0:
        # Only filter the definitions if we have allowed actions
        # (empty list means all actions are allowed)
        definitions = [
            definition for definition in definitions if definition.name in allowed_actions
        ]

    return definitions
