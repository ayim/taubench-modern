"""Utility functions for working with thread state and messages."""

import json
import re
from typing import TYPE_CHECKING, Any

from structlog import get_logger

if TYPE_CHECKING:
    from agent_platform.core.kernel_interfaces.thread_state import ThreadStateInterface

logger = get_logger(__name__)


def get_tool_results_from_thread_state(
    thread_state: "ThreadStateInterface",
    tool_name: str,
) -> list[tuple[int, str]]:
    """Get all tool results for a specific tool from thread state.

    Searches both committed messages and active (uncommitted) message content.

    Args:
        thread_state: The thread state interface with access to thread and active content
        tool_name: The name of the tool to filter by

    Returns:
        List of tuples (sequence_number, result_json_string) ordered
        by sequence_number ascending
    """
    from agent_platform.core.thread import ThreadToolUsageContent

    results = []
    thread = thread_state.kernel.thread

    # Check committed messages in the thread
    for seq_num, message in enumerate(thread.messages):
        for content in message.content:
            if (
                isinstance(content, ThreadToolUsageContent)
                and content.name == tool_name
                and content.status == "finished"
                and content.result is not None
                and content.result != ""
            ):
                results.append((seq_num, content.result))

    # Also check active message content for uncommitted tool results
    active_content = thread_state.active_message_content
    if active_content:
        # Use the next sequence number after the last committed message
        active_seq_num = len(thread.messages)
        for content in active_content:
            if (
                isinstance(content, ThreadToolUsageContent)
                and content.name == tool_name
                and content.status == "finished"
                and content.result is not None
                and content.result != ""
            ):
                results.append((active_seq_num, content.result))

    return results


def get_tool_result_by_ref(
    thread_state: "ThreadStateInterface",
    message_ref_str: str,
) -> dict[str, Any] | Any:
    """Look up a tool result from a message reference like out.tool_name[3].

    Searches both committed messages and active (uncommitted) message content.

    Args:
        thread_state: The thread state interface with access to thread and active content
        message_ref_str: Message reference string (e.g., "out.extract_document[3]",
                        "out.extract_document[-1]")

    Returns:
        Either:
        - The parsed JSON data from the tool result (on success)
        - An error dict with 'error_code' and 'message' keys (on failure)
    """
    thread = thread_state.kernel.thread
    ref_str = message_ref_str.strip()

    # Normalize: LLMs often add .functions in the path (e.g., out.functions.tool_name[index])
    # We ignore this and normalize to out.tool_name[index]
    ref_str = re.sub(r"^out\.functions\.", "out.", ref_str)

    # Match format: out.tool_name[index]
    format_match = re.match(r"^out\.([a-zA-Z_][a-zA-Z0-9_]*)\[(-?\d+)\]$", ref_str)

    if not format_match:
        return {
            "error_code": "invalid_message_reference_format",
            "message": (
                f"Message reference '{ref_str}' is not in valid format. "
                f"Use format like 'out.tool_call_name[3]' or 'out.tool_call_name[-1]'."
            ),
        }

    tool_name = format_match.group(1)
    index = int(format_match.group(2))

    tool_results = get_tool_results_from_thread_state(thread_state, tool_name)

    if not tool_results:
        return {
            "error_code": "tool_not_found",
            "message": (
                f"No completed tool results found for tool '{tool_name}' "
                f"in thread {thread.thread_id}"
            ),
        }

    logger.info(f"Found {len(tool_results)} completed results for tool '{tool_name}'")

    # Handle negative indices (counting from end of results)
    if index < 0:
        result_index = len(tool_results) + index
    else:
        # Convert to 0-indexed for Python lists (1-indexed input)
        result_index = index - 1

    # Validate index
    if result_index < 0 or result_index >= len(tool_results):
        if index < 0:
            valid_range = (
                f"out.{tool_name}[-1] to out.{tool_name}[-{len(tool_results)}]"
                if tool_results
                else f"no completed tool results available for '{tool_name}'"
            )
        else:
            valid_range = (
                f"out.{tool_name}[1] to out.{tool_name}[{len(tool_results)}]"
                if tool_results
                else f"no completed tool results available for '{tool_name}'"
            )
        return {
            "error_code": "invalid_message_reference",
            "message": (
                f"Message reference out.{tool_name}[{index}] is out of range. "
                f"Valid range: {valid_range}"
            ),
        }

    sequence_number, result_str = tool_results[result_index]

    try:
        tool_output = json.loads(result_str)
    except json.JSONDecodeError:
        return {
            "error_code": "invalid_tool_output",
            "message": (
                f"Tool result for out.{tool_name}[{index}] "
                f"(sequence {sequence_number}) is not valid JSON"
            ),
        }

    # Extract the result field if present, otherwise use the whole output
    if "result" in tool_output:
        return tool_output["result"]

    return tool_output
