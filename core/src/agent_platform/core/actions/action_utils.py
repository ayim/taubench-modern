import random
import string
from collections.abc import Callable, Coroutine
from typing import Any

from jsonpointer import JsonPointer, JsonPointerException
from structlog import get_logger

from agent_platform.core.tools.tool_definition import ToolDefinition
from agent_platform.core.utils.url import safe_urljoin

logger = get_logger(__name__)


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


def _build_post_async_function(
    action_url: str,
    api_key: str,
    # Extra headers to be added to the request at
    # tool definition time
    additional_headers: dict | None = None,
) -> Callable[..., Coroutine]:
    async def _post_async_function(
        # Extra headers to be added to the request at
        # tool invocation time
        extra_headers: dict | None = None,
        **args: dict[str, Any],
    ) -> Coroutine:
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

        # We can't have any headers that map to None, so filter them out
        safe_headers = {k: v for k, v in headers.items() if v is not None}

        async with ClientSession() as session:
            async with session.post(
                action_url,
                headers=safe_headers,
                json=args,
            ) as response:
                return await response.json()

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
                    action_url,
                    api_key,
                    additional_headers,
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
