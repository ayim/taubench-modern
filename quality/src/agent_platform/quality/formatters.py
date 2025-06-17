from agent_platform.quality.models import Message, Text, Thought, ToolUse


def messages_to_str(messages: list[Message]) -> str:
    """Convert a list of messages to a XML-like string."""
    all_content = ""
    for msg in messages:
        all_content += "<agent>" if msg.role == "agent" else "<user>"
        for content in msg.content:
            match content:
                case Thought(content=thought):
                    all_content += f"<thought>{thought}</thought>"
                case Text(content=text):
                    all_content += f"<text>{text}</text>"
                case ToolUse(
                    input_as_string=input_as_string,
                    output_as_string=output_as_string,
                    tool_name=tool_name,
                ):
                    all_content += (
                        f"<tool_use><name>{tool_name}</name>"
                        f"<input>{input_as_string}</input>"
                        f"<output>{output_as_string}</output>"
                        f"</tool_use>"
                    )
                case _:
                    raise ValueError(f"Unknown content type: {type(content)}")
        all_content += "</agent>" if msg.role == "agent" else "</user>"
    return all_content
