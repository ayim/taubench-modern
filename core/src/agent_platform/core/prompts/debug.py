from dataclasses import asdict, fields
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agent_platform.core.prompts.prompt import Prompt


def _to_debug_dict_for_prompt(
    prompt: "Prompt", width: int = 100, include: list[str] | None = None
) -> dict:
    """
    Convert the Prompt into a dictionary structure suitable for YAML dumping.

    Args:
        prompt: The prompt to convert
        width: Width for formatting
        include: Optional list of field names to include. If None, includes all fields.
    """
    result = {}
    for f in fields(prompt):
        field_name = f.name

        # We'll skip _finalized as it's internal
        if field_name == "_finalized":
            continue

        # If include is specified, only include those fields
        if include is not None and field_name not in include:
            continue

        value = getattr(prompt, field_name)

        if field_name == "messages":
            # Convert each message in the list
            converted_msgs = []
            for msg in value:
                converted_msgs.append(_to_debug_dict_for_message(msg, width))
            result["messages"] = converted_msgs

        elif field_name == "tools":
            # Tools are presumably ToolDefinition objects
            tool_list = []
            for tool in value:
                tool_dict = asdict(tool)
                # Skip function field as it's a callable
                # (Maybe there's some debug info we could put in the yaml?)
                tool_dict.pop("function")
                tool_list.append(tool_dict)
            result["tools"] = tool_list

        else:
            # For most fields, just store directly
            result[field_name] = value

    return result


def _to_debug_dict_for_message(msg: Any, width: int = 100) -> dict:
    """
    Convert PromptUserMessage, PromptAgentMessage, or SpecialPromptMessage to
    a dictionary suitable for YAML dumping.
    """
    msg_dict = asdict(msg)

    # If the message has 'content', handle each piece
    if hasattr(msg, "content"):
        new_content = []
        for c in msg.content:
            new_content.append(_to_debug_dict_for_content(c, width))
        msg_dict["content"] = new_content

    # We want role, then content, then whatever else, for easier reading
    temp = {
        "role": msg_dict["role"],
        "content": msg_dict["content"] if "content" in msg_dict else None,
        **{k: v for k, v in msg_dict.items() if k not in ["role", "content"]},
    }

    # If no content, remove the key
    if temp["content"] is None:
        temp.pop("content")

    return temp


def _to_debug_dict_for_content(content: Any, width: int = 100) -> dict:
    # We may want to refine field ordering or other formatting here
    # But for now, just convert to a dict and return it
    raw = asdict(content)
    return raw


def to_pretty_yaml(self, width: int = 100, include: list[str] | None = None) -> str:
    """
    Produce a human-friendly YAML string representing this Prompt and
    its messages/content using ruamel.yaml for better formatting control.

    Args:
        width: Maximum line width for formatting
        include: Optional list of field names to include. If None, includes all fields.
                Examples: ["messages"], ["system_instruction", "messages"]
    """
    from io import StringIO

    from ruamel.yaml import YAML
    from ruamel.yaml.scalarstring import LiteralScalarString

    # Fields we always want to format as block scalars
    _block_fields = {"system_instruction", "text", "value"}

    def _prepare_for_yaml(obj, path=()):
        """Process objects for YAML serialization with formatting hints"""
        if isinstance(obj, dict):
            result = {}
            for k, v in obj.items():
                current_path = (*path, k)
                result[k] = _prepare_for_yaml(v, current_path)
            return result
        elif isinstance(obj, list):
            return [_prepare_for_yaml(i, (*path, idx)) for idx, i in enumerate(obj)]
        elif isinstance(obj, str):
            # Force block style for specific fields or long/multiline strings
            last_field = path[-1] if path else None
            should_block = last_field in _block_fields or len(obj) > width or "\n" in obj
            if should_block:
                # Create a tagged object that ruamel will format as block
                return LiteralScalarString(obj)
        return obj

    # Prepare data with formatting hints
    data_dict = _to_debug_dict_for_prompt(self, width, include)
    formatted_data = _prepare_for_yaml(data_dict)

    # Configure and use ruamel.yaml
    yaml = YAML()
    yaml.indent(mapping=2, sequence=4, offset=2)
    yaml.width = width
    yaml.default_flow_style = False

    # Dump to string
    string_stream = StringIO()
    yaml.dump(formatted_data, string_stream)
    return string_stream.getvalue()
