import json
import os
import random
import string
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from enum import IntEnum
from http import HTTPStatus
from typing import Any, TypedDict

import httpx
from httpx_retries import Retry, RetryTransport
from jsonpointer import JsonPointer, JsonPointerException
from structlog import get_logger

from agent_platform.core.configurations.base import Configuration, FieldMetadata
from agent_platform.core.tools.tool_definition import ToolDefinition
from agent_platform.core.utils.url import safe_urljoin

logger = get_logger(__name__)

# This is the default API key for the action server in case none is provided.
# This is a random string that is used to authenticate with the action server.
# It is not used for any other purpose.
DEFAULT_API_KEY = "NO-API-KEY-CONFIGURED"


@dataclass(frozen=True)
class ActionUtilsRetryConfig(Configuration):
    total: int = field(
        default=3,
        metadata=FieldMetadata(
            description="The total number of retries to attempt.",
        ),
    )
    backoff_factor: float = field(
        default=1.0,
        metadata=FieldMetadata(
            description="The backoff factor to use for retries.",
        ),
    )
    status_forcelist: set[int] = field(
        default_factory=lambda: {429, 500, 502, 503, 504},
        metadata=FieldMetadata(
            description="The status codes that should be retried.",
        ),
    )
    allowed_methods: list[str] = field(
        default_factory=lambda: ["GET"],
        metadata=FieldMetadata(
            description="The methods that should be retried.",
        ),
    )


# Retry configuration for read-only operations (spec fetching, status checks)
def _get_read_retry_transport() -> RetryTransport:
    return RetryTransport(
        retry=Retry(
            # This looks odd, but our config system is set up
            # to access via attributes on the class
            total=ActionUtilsRetryConfig.total,
            backoff_factor=ActionUtilsRetryConfig.backoff_factor,
            status_forcelist=ActionUtilsRetryConfig.status_forcelist,
            allowed_methods=ActionUtilsRetryConfig.allowed_methods,
        )
    )


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


@dataclass
class ActionResponse:
    """Response from action server."""

    result: Any | None
    error: str | None


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
    client: httpx.AsyncClient,
    base_url: str,
    api_key: str,
    request_id: str,
) -> str | None:
    """Get the run ID from a request ID.

    Args:
        client: The httpx AsyncClient to use (should have retry transport)
        base_url: The base URL of the action server
        api_key: The API key for authentication
        request_id: The request ID to get the run ID for

    Returns:
        The run ID if found, None otherwise
    """
    run_id_url = f"{base_url}/api/runs/run-id-from-request-id/{request_id}"
    bearer_api_key = api_key or DEFAULT_API_KEY
    try:
        response = await client.get(
            run_id_url,
            headers={
                "Authorization": f"Bearer {bearer_api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
        )
        if response.status_code == HTTPStatus.OK:
            result = response.json()
            run_id = result.get("run_id")
            if run_id:
                logger.info(f"Found run ID {run_id} for request ID {request_id}")
                return run_id
            else:
                logger.warning(f"No run_id found in response for request ID {request_id}")
                return None
        else:
            logger.warning(
                f"Failed to get run ID for request ID {request_id}. Status: {response.status_code}"
            )
            response.raise_for_status()
    except Exception as e:
        logger.error(f"Error getting run ID from request ID: {e!s}", exc_info=True)
        return None


async def _check_action_status(
    client: httpx.AsyncClient,
    base_url: str,
    api_key: str,
    async_action_run_id: str,
    action_server_id: str,
) -> ActionStatusResponse:
    """Check the status of an action run.

    Args:
        client: The httpx AsyncClient to use (should have retry transport for resilience)
        base_url: The base URL of the action server (e.g., http://localhost:8080)
        api_key: The API key for authentication
        async_action_run_id: The ID of the async action run
        action_server_id: The ID of the action server

    Returns:
        dict: The response from the action server containing the run status
    """
    try:
        bearer_api_key = api_key or DEFAULT_API_KEY
        headers = {
            "Authorization": f"Bearer {bearer_api_key}",
            "Content-Type": "application/json",
            "x-action-server-pod-ip": action_server_id,
        }

        response = await client.get(f"{base_url}/api/runs/{async_action_run_id}", headers=headers)

        if response.status_code != HTTPStatus.OK:
            logger.warning(
                f"Action status check failed: HTTP {response.status_code} "
                f"for run {async_action_run_id}"
            )
            return {"status": -1}  # Indicate error with status -1

        return response.json()
    except Exception as e:
        logger.error(f"Error checking action status: {e!s}", exc_info=True)
        return {"status": -1}


def _handle_status_check(status_result: ActionStatusResponse) -> ActionResponse | None:
    """Handle the status check response from an async action.

    Args:
        status: The status code from the action run (can be None)
        status_result: The full status response from the action server

    Returns:
        dict: Response with error and result keys, or None if action is still running
    """
    status = status_result.get("status")
    if status == ActionRunStatus.PASSED:
        return ActionResponse(
            result=status_result.get("result"),
            error=status_result.get("error_message"),
        )
    elif status == ActionRunStatus.FAILED:
        error = status_result.get("error_message")
        result = status_result.get("result")
        if not error:
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except Exception:
                    pass  # Not json
            if isinstance(result, dict):
                error = result.get("error")
                if error and not isinstance(error, str):
                    error = str(error)

        return ActionResponse(
            result=status_result.get("result"),
            error=error or "Action failed",
        )
    elif status == ActionRunStatus.CANCELLED:
        return ActionResponse(
            result=None,
            error="Action was cancelled",
        )
    else:
        logger.debug(f"Retrying action status check (status={status})")
        return None


def _build_post_async_function(
    action_url: str,
    api_key: str,
    # Extra headers to be added to the request at
    # tool definition time
    additional_headers: dict | None = None,
) -> Callable[..., Coroutine[Any, Any, ActionResponse]]:
    async def _post_async_function(
        # Extra headers to be added to the request at
        # tool invocation time
        extra_headers: dict | None = None,
        **args: dict[str, Any],
    ) -> Any:
        import asyncio
        import uuid

        bearer_api_key = api_key or DEFAULT_API_KEY

        characters = string.ascii_letters + string.digits
        action_invocation_id = "".join(random.choice(characters) for _ in range(10))
        headers = {
            "Authorization": f"Bearer {bearer_api_key}",
            "Content-Type": "application/json",
            "x-action_invocation_id": action_invocation_id,
            **(additional_headers or {}),
            **(extra_headers or {}),
        }

        # Only add async headers if SEMA4AI_AGENT_SERVER_ENABLE_ASYNC_ACTION is true
        if os.getenv("SEMA4AI_AGENT_SERVER_ENABLE_ASYNC_ACTION", "true").lower() == "true":
            # The timeout can be a float (like 0.1 seconds), so handle it properly
            timeout_seconds = os.getenv("ACTIONS_ASYNC_TIMEOUT", "20")
            headers.update(
                {
                    "x-actions-request-id": str(uuid.uuid4()),
                    "x-actions-async-timeout": str(timeout_seconds),
                    "x-actions-async-callback": "",  # No callback URL
                }
            )

        # We can't have any headers that map to None, so filter them out
        safe_headers = {k: v for k, v in headers.items() if v is not None}

        # Use httpx without retries for action execution (actions need NOT be idempotent
        # and we don't want to accidentally double-execute them)
        async with httpx.AsyncClient(timeout=300.0) as action_client:
            logger.info(f"Executing action: {action_url}")
            response = await action_client.post(
                action_url,
                headers=safe_headers,
                json=args,
            )
            result = response.json()

            # In case of async action, we need to poll for the status of the action
            # The action server will set the x-action-async-completion header to 1
            # if the action is async.
            # Ref: https://github.com/Sema4AI/actions/blob/master/action_server/docs/guides/16-run-action-sync-async.md
            is_async_action = response.headers.get("x-action-async-completion") == "1"
            async_action_run_id = response.headers.get("x-action-server-run-id")
            action_server_id = response.headers.get("x-action-server-pod-ip", "")
            if is_async_action:
                logger.info(f"Action running async, polling for completion: {async_action_run_id}")
                # Extract base URL from the action URL
                base_url = action_url.split("/api/actions/")[0]

                # Start polling for action server status
                # Default: 60 minutes with 10 second intervals
                max_retries = int(os.getenv("ACTIONS_ASYNC_MAX_RETRIES", "600"))
                # Default: 10 seconds between retries
                retry_interval = float(os.getenv("ACTIONS_ASYNC_RETRY_INTERVAL", "10"))
                retries = 0

                # Use a separate client with retry transport for status checks
                # (these are read-only and should be more resilient)
                async with httpx.AsyncClient(
                    transport=_get_read_retry_transport(), timeout=60.0
                ) as status_client:
                    while retries < max_retries:
                        try:
                            if async_action_run_id:
                                # Check action status
                                status_result = await _check_action_status(
                                    client=status_client,
                                    base_url=base_url,
                                    api_key=api_key,
                                    async_action_run_id=async_action_run_id,
                                    action_server_id=action_server_id,
                                )
                                # Handle different status codes
                                status_response = _handle_status_check(status_result)
                                if status_response is not None:
                                    if status_response.error:
                                        logger.warning(
                                            f"Async action failed: {status_response.error}",
                                        )
                                    else:
                                        logger.info("Async action completed successfully")
                                    return status_response

                            await asyncio.sleep(retry_interval)
                            retries += 1

                        except Exception as e:
                            logger.error(
                                f"Error checking async action status: {e!s}", exc_info=True
                            )
                            await asyncio.sleep(retry_interval)
                            retries += 1

                    # If we get here, we've timed out
                    logger.warning(f"Async action timed out after {max_retries} retries")
                    return ActionResponse(
                        result=None,
                        error="Async action did not complete after timeout",
                    )
            else:
                logger.info("Action completed synchronously")
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
    # Get the spec url
    if not url.startswith("http"):
        url = "http://" + url
    spec_url = safe_urljoin(url, "openapi.json")

    logger.info(f"Fetching OpenAPI spec from action-server: {spec_url}")

    # Use httpx with retry transport for fetching OpenAPI specs
    # (this is a read-only operation that should be resilient to transient failures)
    async with httpx.AsyncClient(transport=_get_read_retry_transport(), timeout=60.0) as client:
        response = await client.get(spec_url)
        response.raise_for_status()  # Raise for HTTP errors
        spec = response.json()

    definitions = _openapi_spec_to_tool_definitions(url, api_key, spec, additional_headers)
    if len(allowed_actions) > 0:
        # Only filter the definitions if we have allowed actions
        # (empty list means all actions are allowed)
        original_count = len(definitions)
        definitions = [
            definition for definition in definitions if definition.name in allowed_actions
        ]
        logger.info(
            f"Filtered {original_count} -> {len(definitions)} tools (allowed: {allowed_actions})"
        )

    logger.info(f"Found {len(definitions)} tool definitions for action-server @ {url}")
    if len(definitions) == 0:
        logger.warning(f"No tool definitions found for action-server @ {url}!")

    return definitions
