from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from types import UnionType
from typing import TYPE_CHECKING, Any, Literal, Union, cast

from agent_platform.core.kernel_interfaces.kernel_mixin import UsesKernelMixin
from agent_platform.core.platforms.base import PlatformConverters
from agent_platform.core.platforms.google.prompts import GooglePrompt
from agent_platform.core.prompts import (
    Prompt,
    PromptAgentMessage,
    PromptAudioContent,
    PromptImageContent,
    PromptMessageContent,
    PromptReasoningContent,
    PromptTextContent,
    PromptToolResultContent,
    PromptToolUseContent,
    PromptUserMessage,
)
from agent_platform.core.prompts.content.document import PromptDocumentContent
from agent_platform.core.tools.tool_definition import ToolDefinition

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from google.genai import types
    from google.genai.types import Content, Part


class GoogleConverters(PlatformConverters, UsesKernelMixin):
    """Converters that transform agent-server prompt types to Google types."""

    async def convert_text_content(
        self,
        content: PromptTextContent,
    ) -> Part:
        """Converts text content to Google format."""
        from google.genai.types import Part

        return Part(text=content.text)

    async def convert_image_content(
        self,
        content: PromptImageContent,
    ) -> Part:
        """Converts image content to Google format."""
        raise NotImplementedError("Image not supported yet")

    async def convert_audio_content(
        self,
        content: PromptAudioContent,
    ) -> Part:
        """Converts audio content to Google format."""
        raise NotImplementedError("Audio not supported yet")

    async def convert_tool_use_content(
        self,
        content: PromptToolUseContent,
    ) -> Part:
        """Converts tool use content to Google format."""
        from google.genai.types import FunctionCall, Part

        return Part(
            function_call=FunctionCall(name=content.tool_name, args=content.tool_input),
        )

    async def convert_reasoning_content(
        self,
        content: PromptReasoningContent,
    ) -> Part:
        """Converts reasoning content to Google format."""
        from google.genai.types import Part

        # signature for us was a `.hex()` of the bytes, so
        # now we need to convert it back to bytes
        signature_bytes = None
        if content.signature:
            signature_bytes = bytes.fromhex(content.signature)

        return Part(
            text=content.reasoning,
            thought_signature=signature_bytes,
            thought=True,
        )

    async def convert_tool_result_content(
        self,
        content: PromptToolResultContent,
    ) -> Part:
        """Converts tool result content to Google format."""
        from google.genai.types import FunctionResponse, Part

        text_content = ""
        for content_item in content.content:
            if isinstance(content_item, PromptTextContent):
                text_content += content_item.text + "\n"
            elif isinstance(content_item, PromptImageContent):
                raise NotImplementedError("Image not supported yet")
            elif isinstance(content_item, PromptAudioContent):
                raise NotImplementedError("Audio not supported yet")
            elif isinstance(content_item, PromptDocumentContent):
                raise NotImplementedError("Document not supported yet")
            else:
                raise ValueError(f"Unsupported content type: {type(content_item)}")

        # Format as a function response
        return Part(
            function_response=FunctionResponse(
                name=content.tool_name,
                response={"content": text_content.strip()},
            ),
        )

    async def convert_document_content(
        self,
        content: PromptDocumentContent,
    ) -> Part:
        """Converts document content to Google format."""
        raise NotImplementedError("Document not supported yet")

    async def _reverse_role_map(self, role: str) -> Literal["user", "model"]:
        """Reverse the role map.

        Args:
            role: The role to reverse.

        Returns:
            The corresponding Google role name.

        Raises:
            ValueError: If the role is not found in the map.
        """
        match role:
            case "user":
                return "user"
            case "agent":
                return "model"
            case _:
                raise ValueError(f"Role '{role}' not found in Google role map")

    async def _process_message_content(
        self,
        content_list: Sequence[PromptMessageContent],
    ) -> list[Part]:
        """Process prompt message content and organize into parts.

        Args:
            content_list: The list of content to process.

        Returns:
            A list of content parts for Google API.
        """
        from google.genai.types import Part

        parts = []

        for content in content_list:
            if isinstance(content, PromptTextContent):
                parts.append(cast(Part, await self.convert_text_content(content)))
            elif isinstance(content, PromptToolUseContent):
                parts.append(cast(Part, await self.convert_tool_use_content(content)))
            elif isinstance(content, PromptToolResultContent):
                parts.append(
                    cast(Part, await self.convert_tool_result_content(content)),
                )
            elif isinstance(content, PromptReasoningContent):
                parts.append(cast(Part, await self.convert_reasoning_content(content)))
            elif isinstance(content, PromptImageContent):
                raise NotImplementedError("Image content not supported yet")
            elif isinstance(content, PromptAudioContent):
                raise NotImplementedError("Audio content not supported yet")
            elif isinstance(content, PromptDocumentContent):
                raise NotImplementedError("Document content not supported yet")

        return parts

    async def _convert_system_instruction(
        self,
        system_instruction: str | None,
    ) -> Content | None:
        """Convert system instruction to Google format.

        Args:
            system_instruction: The system instruction to convert.

        Returns:
            The converted system instruction.
        """
        from google.genai.types import Content, Part

        if system_instruction is None:
            return None

        return Content(
            parts=[Part(text=system_instruction)],
            role="user",
        )

    async def _convert_messages(
        self,
        messages: list[PromptUserMessage | PromptAgentMessage],
    ) -> list[Content]:
        """Convert prompt messages to Google message format.

        Args:
            messages: The list of prompt messages to convert.

        Returns:
            The list of Google message parameters.
        """
        from google.genai.types import Content

        converted_messages = []

        for message in messages:
            # Process the message content to get parts
            processed_parts = await self._process_message_content(message.content)

            if processed_parts:
                # Get the appropriate Google role
                google_role = await self._reverse_role_map(message.role)

                # Add the message
                converted_messages.append(
                    Content(
                        parts=processed_parts,
                        role=google_role,
                    ),
                )

        return converted_messages

    def _fix_schema_types(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Fix schema types for Google API compatibility.

        Args:
            schema: The original schema.

        Returns:
            The fixed schema.
        """
        if not schema:
            return schema

        # Deep copy to avoid modifying the original
        fixed_schema = schema.copy()

        # Remove unsupported fields
        self._remove_unsupported_fields(fixed_schema)

        # If schema has properties, process each property
        if "properties" in fixed_schema and isinstance(
            fixed_schema["properties"],
            dict,
        ):
            self._fix_property_schemas(fixed_schema["properties"])

        return fixed_schema

    def _remove_unsupported_fields(self, schema: dict[str, Any]) -> None:
        """Remove fields not supported by Google API from schema.

        Args:
            schema: The schema to modify.
        """
        if "strict" in schema:
            logger.debug(f"Removing 'strict' from schema: {schema['strict']}")
            del schema["strict"]

        if "additionalProperties" in schema:
            logger.debug(
                f"Removing 'additionalProperties' from schema: {schema['additionalProperties']}",
            )
            del schema["additionalProperties"]

    def _fix_property_schemas(self, properties: dict[str, Any]) -> None:
        """Fix property schemas for Google API compatibility.

        Args:
            properties: The properties dictionary to fix.
        """
        # Log all properties for debugging
        logger.debug(f"Fixing schema with {len(properties)} properties")

        for prop_name, prop_schema in list(properties.items()):
            if not isinstance(prop_schema, dict):
                logger.warning(f"Property {prop_name} is not a dict: {prop_schema}")
                continue

            # Handle union types (like ['string', 'null'] or multiple types)
            if "type" in prop_schema and isinstance(prop_schema["type"], list):
                self._handle_union_types(prop_name, prop_schema)

            # Ensure all properties have a type
            if "type" not in prop_schema:
                logger.debug(f"Adding missing type to property {prop_name}")
                prop_schema["type"] = "string"  # Default to string if no type specified

            # Handle items field more carefully
            self._fix_items_field(prop_name, prop_schema)

            # For array types, ensure items is properly formatted
            if prop_schema.get("type") == "array" and "items" in prop_schema:
                self._ensure_array_items_type(prop_name, prop_schema)

            # Recursively fix nested objects
            if prop_schema.get("type") == "object" and "properties" in prop_schema:
                logger.debug(f"Recursively fixing nested object in {prop_name}")
                fixed_nested_schema = self._fix_schema_types(prop_schema)
                properties[prop_name] = fixed_nested_schema
                continue

            # Make sure enums are strings if not already
            if "enum" in prop_schema and isinstance(prop_schema["enum"], list):
                self._ensure_enum_values_are_strings(prop_name, prop_schema)

            # Update the property in the schema
            properties[prop_name] = prop_schema

    def _handle_union_types(self, prop_name: str, prop_schema: dict[str, Any]) -> None:
        """Handle union types in schema.

        Args:
            prop_name: The property name.
            prop_schema: The property schema to modify.
        """
        logger.debug(
            f"Found union type in property {prop_name}: {prop_schema['type']}",
        )

        # Save the original type list for documentation
        original_types = prop_schema["type"]

        # If null is in the type list, make it nullable instead
        if "null" in original_types:
            self._handle_nullable_union(prop_name, prop_schema, original_types)
        else:
            # For multiple non-null types, choose the first one
            self._handle_multi_type_union(prop_name, prop_schema, original_types)

    def _handle_nullable_union(
        self,
        prop_name: str,
        prop_schema: dict[str, Any],
        original_types: list[str],
    ) -> None:
        """Handle union types that include null.

        Args:
            prop_name: The property name.
            prop_schema: The property schema to modify.
            original_types: The original type list.
        """
        # Find the first non-null type to use as primary type
        non_null_types = [t for t in original_types if t != "null"]
        if non_null_types:
            primary_type = non_null_types[0]
            prop_schema["type"] = primary_type
            # Add nullable flag if not already present
            prop_schema["nullable"] = True
            logger.debug(
                f"Converted union with null to {primary_type} with nullable=True for {prop_name}",
            )
        else:
            # If only null is present, default to string
            prop_schema["type"] = "string"
            prop_schema["nullable"] = True
            logger.debug(
                f"Converted null-only type to string with nullable=True for {prop_name}",
            )

    def _handle_multi_type_union(
        self,
        prop_name: str,
        prop_schema: dict[str, Any],
        original_types: list[str],
    ) -> None:
        """Handle union types with multiple non-null types.

        Args:
            prop_name: The property name.
            prop_schema: The property schema to modify.
            original_types: The original type list.
        """
        # For multiple non-null types (like ['string', 'integer']),
        # choose the first one. Google API doesn't support true union types
        primary_type = original_types[0]
        logger.debug(
            f"Using {primary_type} as primary type for union in {prop_name}",
        )
        prop_schema["type"] = primary_type

        # Add a note in the description about alternative types
        if "description" in prop_schema:
            prop_schema["description"] += f" (Possible types: {', '.join(original_types)})"
        else:
            prop_schema["description"] = f"Accepts multiple types: {', '.join(original_types)}"

    def _fix_items_field(self, prop_name: str, prop_schema: dict[str, Any]) -> None:
        """Fix items field in schema.

        Args:
            prop_name: The property name.
            prop_schema: The property schema to modify.
        """
        # If the property has an empty items field, remove it unless the type
        # is array
        if "items" in prop_schema and not prop_schema["items"]:
            if prop_schema.get("type") == "array":
                # For arrays, ensure items has a type
                prop_schema["items"] = {"type": "string"}
            else:
                # For non-arrays, remove the empty items field
                logger.debug(
                    f"Removing empty items field from non-array property {prop_name}",
                )
                del prop_schema["items"]

    def _ensure_array_items_type(
        self,
        prop_name: str,
        prop_schema: dict[str, Any],
    ) -> None:
        """Ensure array items have a type.

        Args:
            prop_name: The property name.
            prop_schema: The property schema to modify.
        """
        if not isinstance(prop_schema["items"], dict):
            logger.debug(
                f"Converting 'items' in {prop_name} to a dict with type",
            )
            prop_schema["items"] = {"type": "string"}
        elif "type" not in prop_schema["items"]:
            logger.debug(f"Adding missing type to 'items' in {prop_name}")
            prop_schema["items"]["type"] = "string"

    def _ensure_enum_values_are_strings(
        self,
        prop_name: str,
        prop_schema: dict[str, Any],
    ) -> None:
        """Ensure enum values are strings.

        Args:
            prop_name: The property name.
            prop_schema: The property schema to modify.
        """
        logger.debug(f"Ensuring enum values are strings in {prop_name}")
        prop_schema["enum"] = [str(e) if not isinstance(e, str) else e for e in prop_schema["enum"]]

    async def _convert_tools(
        self,
        tools: list[ToolDefinition],
    ) -> list[types.Tool]:
        """Convert tool definitions to Google tool parameters.

        Args:
            tools: The list of tool definitions to convert.

        Returns:
            The list of Google tool parameters.
        """
        converted_tools = []

        for tool in tools:
            logger.debug(f"Converting tool: {tool.name}")

            # Fix schema
            fixed_schema = await self._prepare_tool_schema(tool)

            # Create function declaration and add to converted tools
            converted_tool = await self._create_tool_declaration(tool, fixed_schema)
            if converted_tool:
                converted_tools.append(converted_tool)

        return converted_tools

    async def _prepare_tool_schema(self, tool: ToolDefinition) -> dict[str, Any]:
        """Prepare and fix tool schema for Google API.

        Args:
            tool: The tool definition.

        Returns:
            The fixed schema.
        """
        # Start with a minimal schema as fallback
        minimal_schema = {"type": "object", "properties": {}}

        if not tool.input_schema:
            logger.warning(f"Tool {tool.name} has no input schema")
            return minimal_schema

        try:
            # Log the original schema
            logger.debug(
                f"Original schema for {tool.name}: {json.dumps(tool.input_schema)}",
            )

            # Apply fixes to make the schema compatible with Google's API
            fixed_schema = self._fix_schema_types(tool.input_schema)
            logger.debug(
                f"Fixed schema for {tool.name}: {json.dumps(fixed_schema)}",
            )
            return fixed_schema

        except Exception as e:
            logger.error(f"Error fixing schema for tool {tool.name}: {e}")
            logger.error(f"Original schema: {tool.input_schema}")

            # Continue with a simplified schema created from parameter types
            logger.debug(f"Creating a simplified schema for {tool.name}")
            return self._create_schema_from_param_types(tool)

    def _create_schema_from_param_types(self, tool: ToolDefinition) -> dict[str, Any]:
        """Create a schema from parameter types.

        Args:
            tool: The tool definition.

        Returns:
            The created schema.
        """
        fixed_schema = {"type": "object", "properties": {}}

        for param_name, param_type in getattr(tool, "_parameter_types", {}).items():
            is_typing_union = hasattr(param_type, "__origin__") and param_type.__origin__ is Union
            if is_typing_union or isinstance(param_type, UnionType):
                self._add_union_param_to_schema(fixed_schema, param_name, param_type)
            else:
                self._add_basic_param_to_schema(fixed_schema, param_name, param_type)

        return fixed_schema

    def _add_union_param_to_schema(
        self,
        schema: dict[str, Any],
        param_name: str,
        param_type: Any,
    ) -> None:
        """Add a union parameter to the schema.

        Args:
            schema: The schema to modify.
            param_name: The parameter name.
            param_type: The parameter type.
        """
        # Handle Union types like Union[str, int] or
        # Optional[str] (Union[str, None])
        args = param_type.__args__

        if type(None) in args:
            # This is an Optional type (contains None)
            non_none_types = [t for t in args if t is not type(None)]

            if non_none_types:
                # Use the first non-None type
                primary_type = non_none_types[0]
                schema["properties"][param_name] = {
                    "type": self._get_json_schema_type(primary_type),
                    "nullable": True,
                }
            else:
                # Fallback for Union[None]
                schema["properties"][param_name] = {
                    "type": "string",
                    "nullable": True,
                }
        else:
            # This is a regular Union - use the first type
            primary_type = args[0]
            schema["properties"][param_name] = {
                "type": self._get_json_schema_type(primary_type),
            }

    def _add_basic_param_to_schema(
        self,
        schema: dict[str, Any],
        param_name: str,
        param_type: Any,
    ) -> None:
        """Add a basic parameter to the schema.

        Args:
            schema: The schema to modify.
            param_name: The parameter name.
            param_type: The parameter type.
        """
        if param_type is str:
            schema["properties"][param_name] = {"type": "string"}
        elif param_type is int:
            schema["properties"][param_name] = {"type": "integer"}
        elif param_type is float:
            schema["properties"][param_name] = {"type": "number"}
        elif param_type is bool:
            schema["properties"][param_name] = {"type": "boolean"}
        elif param_type is type(None):
            # Handle explicit None type
            schema["properties"][param_name] = {
                "type": "string",
                "nullable": True,
            }
        else:
            # Default to string for any other type
            schema["properties"][param_name] = {"type": "string"}

    async def _create_tool_declaration(
        self,
        tool: ToolDefinition,
        schema: dict[str, Any],
    ) -> types.Tool | None:
        """Create function declaration for tool.

        Args:
            tool: The tool definition.
            schema: The tool schema.

        Returns:
            The converted tool, or None if conversion failed.
        """
        from google.genai import types
        from google.genai.types import Schema

        try:
            # Create function declaration
            function_declaration = types.FunctionDeclaration(
                name=tool.name,
                description=tool.description or "",
                parameters=cast(Schema, schema),
            )

            converted_tool = types.Tool(
                function_declarations=[function_declaration],
            )
            logger.debug(f"Successfully converted tool: {tool.name}")
            return converted_tool

        except Exception as e:
            logger.error(
                f"Failed to create function declaration for {tool.name}: {e}",
            )
            logger.error(f"Schema after fixing: {schema}")

            # Try with minimal schema as fallback
            return await self._create_tool_with_minimal_schema(tool)

    async def _create_tool_with_minimal_schema(
        self,
        tool: ToolDefinition,
    ) -> types.Tool | None:
        """Create tool with minimal schema as fallback.

        Args:
            tool: The tool definition.

        Returns:
            The converted tool, or None if conversion failed.
        """
        from google.genai import types
        from google.genai.types import Schema

        try:
            # Try with a minimal schema
            minimal_schema = {"type": "object", "properties": {}}
            logger.debug(f"Attempting with minimal schema for {tool.name}")

            function_declaration = types.FunctionDeclaration(
                name=tool.name,
                description=tool.description or "",
                parameters=cast(Schema, minimal_schema),
            )

            converted_tool = types.Tool(
                function_declarations=[function_declaration],
            )

            logger.debug(
                f"Successful fallback conversion for tool: {tool.name}",
            )
            return converted_tool

        except Exception as e2:
            logger.error(f"Fallback also failed for {tool.name}: {e2}")
            # Skip this tool if both attempts fail
            return None

    async def convert_prompt(
        self,
        prompt: Prompt,
        model_id: str | None = None,
    ) -> GooglePrompt:
        """Convert a prompt to Google format.

        Args:
            prompt: The prompt to convert.
            model_id: Optional model ID.

        Returns:
            The converted prompt.
        """
        # Convert messages
        messages = await self._convert_messages(prompt.finalized_messages)

        # Convert system instruction if present
        if prompt.system_instruction:
            system_message = await self._convert_system_instruction(
                prompt.system_instruction,
            )
            if system_message:
                messages.insert(0, system_message)

        thinking_budget, thinking_level = self._determine_reasoning_settings(
            model_id,
            prompt.minimize_reasoning,
        )

        # Convert tools if present
        tools = None
        if prompt.tools:
            logger.debug(f"Converting {len(prompt.tools)} tools")
            tools = await self._convert_tools(prompt.tools)

        return GooglePrompt(
            contents=messages,
            tools=tools,
            temperature=prompt.temperature or 0.0,
            thinking_budget=thinking_budget,
            thinking_level=thinking_level,
            top_p=prompt.top_p or 1.0,
            max_output_tokens=prompt.max_output_tokens or 4096,
        )

    def _determine_reasoning_settings(
        self,
        model_id: str | None,
        minimize_reasoning: bool,
    ) -> tuple[int, str | None]:
        """Return the thinking budget/level for the provided model."""
        if not model_id:
            return 0, None

        if "gemini-3" in model_id:
            return 0, self._gemini3_thinking_level(model_id, minimize_reasoning)

        thinking_budget = self._resolve_reasoning_budget(model_id)
        final_budget = self._apply_minimize_reasoning_budget(
            model_id,
            thinking_budget,
            minimize_reasoning,
        )
        return final_budget, None

    def _gemini3_thinking_level(self, model_id: str, minimize_reasoning: bool) -> str:
        if minimize_reasoning:
            return "low"

        suffix_map = {
            "-low": "low",
            "-medium": "low",
            "-high": "high",
        }
        for suffix, level in suffix_map.items():
            if model_id.endswith(suffix):
                return level

        return "high"

    def _resolve_reasoning_budget(self, model_id: str) -> int:
        suffix_budget_map = {
            "-lite": (512, "lite"),
            "-low": (1024, "low"),
            "-medium": (8192, "medium"),
            "-high": (24576, "high"),
        }
        for suffix, (budget, label) in suffix_budget_map.items():
            if model_id.endswith(suffix):
                logger.info(f"Using {model_id} with {label} thinking budget ({budget})")
                return budget

        if "-pro" in model_id:
            default_budget = 1024
            logger.info(
                f"Model {model_id} requires reasoning budget, defaulting to {default_budget}",
            )
            return default_budget

        return 0

    def _apply_minimize_reasoning_budget(
        self,
        model_id: str,
        thinking_budget: int,
        minimize_reasoning: bool,
    ) -> int:
        if not minimize_reasoning:
            return thinking_budget

        if "-pro" in model_id:
            minimum_budget = 1024
            logger.info(
                f"Model {model_id} is a Gemini Pro model, "
                f"setting minimum thinking budget to {minimum_budget}",
            )
            return minimum_budget

        return 0

    def _get_json_schema_type(self, python_type: type) -> str:
        """Convert Python type to JSON Schema type.

        Args:
            python_type: Python type to convert.

        Returns:
            JSON Schema type string.
        """
        # Define type mappings
        python_to_json_schema = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
        }

        # Check direct type matches
        if python_type in python_to_json_schema:
            return python_to_json_schema[python_type]

        # Handle list types
        if python_type is list:
            return "array"

        # Handle parametrized types like list[str], dict[str, Any]
        if hasattr(python_type, "__origin__"):
            origin = python_type.__origin__
            if origin is list:
                return "array"
            if origin is dict:
                return "object"

        # Handle dict types
        if python_type is dict:
            return "object"

        # Default to string for complex types
        return "string"
