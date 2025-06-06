from dataclasses import dataclass, field, fields

from agent_platform.core.responses.content.tool_use import ResponseToolUseContent
from agent_platform.core.responses.streaming import (
    ResponseStreamSinkBase,
    ToolUseResponseStreamSink,
    XmlTagResponseStreamSink,
)
from agent_platform.core.tools.tool_definition import ToolDefinition

PendingToolCall = tuple[ToolDefinition, ResponseToolUseContent]


@dataclass
class StateBase:
    """
    Base state dataclass that validates that all scoped fields are JSON serializable.

    Scoped fields are those with a metadata 'scope' ('user', 'thread', or 'agent').
    This ensures that areas of state intended for JSON persistence will not cause errors
    when being backed by a JSON database.
    """

    class Sinks:
        def __init__(self, state: "StateBase"):
            self.state = state

        @property
        def pending_tool_calls(self) -> ToolUseResponseStreamSink:
            """
            A sink that will appending incoming tool calls to the
            pending_tool_calls field.
            """

            async def _on_tool_complete(
                content: ResponseToolUseContent,
                tool_def: ToolDefinition | None,
            ) -> None:
                if tool_def is not None:
                    self.state.pending_tool_calls.append((tool_def, content))

            return ToolUseResponseStreamSink(
                on_tool_complete=_on_tool_complete,
            )

        def tool_use_sink(
            self,
            field_name: str,
        ) -> ResponseStreamSinkBase:
            """
            Create a sink that will write update the value of the given
            field when a tool call completes streaming.

            Args:
                field_name: The name of the field to update when the tool
                    call completes streaming.

            Returns:
                A sink that will write update the value of the given
                field when a tool call completes streaming.
            """
            previous_value = getattr(self.state, field_name, [])

            async def _on_tool_complete(
                content: ResponseToolUseContent,
                tool_def: ToolDefinition | None,
            ) -> None:
                if tool_def is not None:
                    setattr(
                        self.state,
                        field_name,
                        [*previous_value, (tool_def, content)],
                    )

            return ToolUseResponseStreamSink(
                on_tool_complete=_on_tool_complete,
            )

        def xml_tag_sink(
            self,
            field_name: str,
            expected_preceding_tag: str | None = None,
            expected_next_tag: str | None = None,
        ) -> ResponseStreamSinkBase:
            """
            Create a sink that will write update the value of the given
            field when <field_name>value</field_name> occurs in stream.

            Args:
                field_name: The name of the field to update when the tag occurs.

            Returns:
                A sink that will write update the value of the given
                field when <field_name>value</field_name> occurs in stream.
            """

            async def _on_tag_complete(tag: str, content: str) -> None:
                setattr(
                    self.state,
                    field_name,
                    content,
                )

            return XmlTagResponseStreamSink(
                tag=field_name,
                expected_preceding_tag=expected_preceding_tag,
                expected_next_tag=expected_next_tag,
                on_tag_complete=_on_tag_complete,
            )

    def __post_init__(self):
        from json import dumps

        # Iterate over all fields in the dataclass
        for field_obj in fields(self):
            # Check if the field has a 'scope' set in its metadata
            scope = field_obj.metadata.get("scope", None)
            if scope is None or scope not in ["user", "thread", "agent"]:
                continue

            value = getattr(self, field_obj.name)
            try:
                # This will raise an exception if the value is not JSON serializable
                dumps(value)
            except (TypeError, ValueError) as e:
                raise ValueError(
                    f"The field '{field_obj.name}' with scope"
                    f" '{scope}' is not JSON serializable: {e}",
                ) from e

    pending_tool_calls: list[PendingToolCall] = field(
        default_factory=list,
        metadata={
            "description": (
                "A list of tuples of the form (ToolDefinition, ResponseToolUseContent) "
                "where the ToolDefinition is the tool definition associated with the "
                "tool call and the ResponseToolUseContent is the content of the "
                "tool call. Used to track pending tool calls prior to execution."
            ),
        },
    )

    def serialize(self) -> str:
        """
        Serialize the state to a dictionary.
        """
        return str({k: str(v) for k, v in self.__dict__.items()})
