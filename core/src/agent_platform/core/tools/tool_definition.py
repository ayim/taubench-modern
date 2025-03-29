"""ToolDefinition: represents the definition of a tool."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolDefinition:
    """Represents the definition of a tool."""

    name: str = field(metadata={"description": "The name of the tool"})
    """The name of the tool"""

    description: str = field(metadata={"description": "The description of the tool"})
    """The description of the tool"""

    input_schema: dict[str, Any] = field(
        metadata={"description": "The schema of the tool input"},
    )
    """The schema of the tool input"""

    function: Callable[..., Any] = field(
        metadata={"description": "The function that implements the tool"},
    )
    """The function that implements the tool"""

    def model_dump(self) -> dict:
        """Dump the ToolDefinition as a dictionary."""
        # Leave out the function as it's not serializable
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
        }

    @classmethod
    def from_callable(
        cls,
        func: Callable[..., Coroutine[Any, Any, Any]],
        *,
        name: str | None = None,
        description: str | None = None,
        strict: bool = True,
    ) -> "ToolDefinition":
        """Creates a ToolDefinition from an async Python function.

        This method inspects the provided async function and generates a
        ToolDefinition with appropriate name, description, and input schema
        based on the function's signature and metadata.

        Arguments:
            func: An async callable that implements the tool functionality.
            name: Optional name override. If None, uses function's __name__.
            description: Optional description override. If None, uses func's docstring.
            strict: Whether to set 'strict' in the schema for OpenAI function calling.

        Returns:
            ToolDefinition: A fully populated ToolDefinition instance.

        Raises:
            ValueError: If the function is not async, uses *args/**kwargs, or
                has missing required metadata.
        """
        from inspect import iscoroutinefunction, signature

        from agent_platform.core.tools.tool_utils import build_param_schema

        # 1. Ensure the function is async
        if not iscoroutinefunction(func):
            raise ValueError(f"Function '{func.__name__}' must be async.")

        # 2. Determine name and description
        tool_name = name or func.__name__
        doc = description or (func.__doc__ or "").strip() or f"{tool_name} function."

        # 3. Build the JSON schema for parameters
        signature = signature(func)

        properties: dict[str, Any] = {}
        required_fields: list[str] = []

        for param_name, param in signature.parameters.items():
            if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                # Raise on *args/**kwargs for schema generation
                raise ValueError(f"Unsupported parameter kind: {param.kind}")

            # Required if no default given
            is_required = param.default is param.empty

            # Build the param schema
            # We'll rely on `build_param_schema` to introspect type hints & metadata
            param_schema = build_param_schema(
                param_name,
                param.annotation if param.annotation is not param.empty else Any,
                allow_omitted_description=False,
            )
            properties[param_name] = param_schema
            # NOTE: in strict mode, all params must be required
            if is_required or strict:
                required_fields.append(param_name)

        input_schema = {
            "type": "object",
            "properties": properties,
            "required": required_fields,
        }

        if strict:
            # Some folks embed "strict": True, others do not.
            # This is an optional field you might add for usage with certain LLM APIs.
            input_schema["strict"] = True
            # Strict also means no additional properties
            input_schema["additionalProperties"] = False

        return cls(
            name=tool_name,
            description=doc,
            input_schema=input_schema,
            function=func,
        )

    @classmethod
    def model_validate(cls, data: dict) -> "ToolDefinition":
        """Validate and convert a dictionary into a ToolDefinition instance."""
        # TODO: better impl?
        return cls(**data)

