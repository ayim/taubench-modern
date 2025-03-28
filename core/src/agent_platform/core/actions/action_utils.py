from collections.abc import Callable, Coroutine
from typing import Any

from agent_platform.core.tools.tool_definition import ToolDefinition


def _dereference_refs(spec: dict, full_schema: dict) -> dict:
    for key, value in spec.items():
        if isinstance(value, dict) and "$ref" in value:
            ref = value["$ref"]
            spec[key] = _dereference_refs(full_schema[ref], full_schema)
    return spec


def _build_post_async_function(
    action_url: str,
    api_key: str,
    additional_headers: dict | None = None,
) -> Callable[..., Coroutine]:
    async def _post_async_function(**args: dict[str, Any]) -> Coroutine:
        from aiohttp import ClientSession

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            **(additional_headers or {}),
        }

        async with ClientSession() as session:
            async with session.post(action_url, headers=headers, json=args) as response:
                return await response.json()

    return _post_async_function


def _openapi_spec_to_tool_definitions(
    url: str,
    api_key: str,
    spec: dict,
    additional_headers: dict | None = None,
) -> list[ToolDefinition]:
    from urllib.parse import urljoin

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
            action_url = urljoin(url, path.lstrip("/"))

            # Get the requestBody's schema (JSON schema)
            request_body_schema = (
                resolved_spec.get("requestBody", {})
                .get("content", {})
                .get("application/json", {})
                .get("schema", {})
            )

            request_body_args = request_body_schema.get("properties", {})
            request_body_required = request_body_schema.get("required", [])

            # Build args schema
            args_schema = {}
            for arg_name, arg_schema in request_body_args.items():
                args_schema[arg_name] = {
                    "type": arg_schema.get("type", "string"),
                    "description": arg_schema.get("description", ""),
                    "items": arg_schema.get("items", {}),
                }

            # Start building the schema
            tool_definition = ToolDefinition(
                name=resolved_spec.get("operationId"),
                description=resolved_spec.get("summary"),
                input_schema={
                    "type": "object",
                    "properties": args_schema,
                    "required": request_body_required,
                },
                function=_build_post_async_function(
                    action_url, api_key, additional_headers,
                ),
            )

            # Now, reduce the spec to only the required information
            tool_definitions.append(tool_definition)

    return tool_definitions


async def _get_spec_and_build_tool_definitions(
    url: str,
    api_key: str,
    allowed_actions: list[str],
) -> list[ToolDefinition]:
    from urllib.parse import urljoin

    from aiohttp import ClientSession

    # Get the spec url
    if not url.startswith("http"):
        url = "http://" + url
    spec_url = urljoin(url, "openapi.json")

    async with ClientSession() as session:
        async with session.get(spec_url) as response:
            spec = await response.json()

    definitions = _openapi_spec_to_tool_definitions(url, api_key, spec)
    if len(allowed_actions) > 0:
        # Only filter the definitions if we have allowed actions
        # (empty list means all actions are allowed)
        definitions = [
            definition for definition in definitions
            if definition.name in allowed_actions
        ]

    return definitions

