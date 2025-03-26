from dataclasses import dataclass, field
from typing import Literal

from agent_platform_core.thread.content.base import ThreadMessageContent
from agent_platform_core.utils import assert_literal_value_valid


@dataclass
class ThreadQuickActionContent:
    """Represents a quick action in the thread."""

    label: str = field(metadata={"description": "The label of the quick action"})
    """The label of the quick action"""

    value: str = field(
        metadata={
            "description": "The value of the quick action (the text that will be "
                "submitted when the action is clicked)",
        },
    )
    """The value of the quick action (the text that will be submitted when
    the action is clicked)"""

    icon: str | None = field(
        default=None,
        metadata={"description": "The icon of the quick action (if any)"},
    )
    """The icon of the quick action (if any)"""

    def model_dump(self) -> dict:
        """Serializes the quick action content to a dictionary.
        Useful for JSON serialization."""
        return {
            "label": self.label,
            "value": self.value,
            "icon": self.icon,
        }

    @classmethod
    def model_validate(cls, data: dict) -> "ThreadQuickActionContent":
        """Create a thread quick action content from a dictionary."""
        return cls(**data)


@dataclass
class ThreadQuickActionsContent(ThreadMessageContent):
    """Represents a quick actions content component in the thread.

    This class handles quick actions content (think of clickable buttons that allow
    you to easily submit a message without having to type it out).
    """

    actions: list[ThreadQuickActionContent] = field(
        metadata={"description": "The list of quick actions to display"},
    )
    """The list of quick actions to display"""

    kind: Literal["quick_actions"] = field(
        default="quick_actions",
        metadata={"description": "Content kind: always 'quick_actions'"},
        init=False,
    )
    """Content kind: always 'quick_actions'"""

    completed: bool = field(
        default=False,
        metadata={"description": "Whether the quick actions are completed"},
    )
    """Whether the quick actions are completed"""

    def __post_init__(self) -> None:
        """Validates the message content type and quick actions after initialization.

        Raises:
            AssertionError: If the kind field doesn't match the literal "quick_actions".
            ValueError: If the actions field is empty.
        """
        assert_literal_value_valid(self, "kind")

        # Make sure we have at least one action
        if len(self.actions) == 0:
            raise ValueError("Actions value cannot be empty")

        # Make sure no two actions have the same label
        labels = [action.label for action in self.actions]
        if len(labels) != len(set(labels)):
            raise ValueError("All actions must have unique labels")

    def as_text_content(self) -> str:
        """Converts the quick actions content to a text content component."""
        from html import escape

        actions_as_strs = []
        for action in self.actions:
            # <choice data-message="Valid message" data-icon="IconInfo">Label</choice>
            # ^ Example of how the UX is expecting the inlined HTML to look
            icon_attr = (
                f'data-icon="{escape(action.icon)}"' if action.icon else ""
            )
            data_attr = f'data-message="{escape(action.value, quote=True)}"'
            actions_as_strs.append(
                f"<choice {data_attr} {icon_attr}>{action.label}</choice>",
            )

        actions_str = "\n".join(actions_as_strs)
        return f"<quick_actions>\n{actions_str}\n</quick_actions>"

    def model_dump(self) -> dict:
        """Serializes the quick actions content to a dictionary.
        Useful for JSON serialization."""
        return {
            **super().model_dump(),
            "actions": [action.model_dump() for action in self.actions],
        }

    @classmethod
    def model_validate(cls, data: dict) -> "ThreadQuickActionsContent":
        """Create a thread quick actions content from a dictionary."""
        data = data.copy()
        actions = [
            ThreadQuickActionContent.model_validate(action)
            for action in data.pop("actions")
        ]
        return cls(**data, actions=actions)


ThreadMessageContent.register_content_kind("quick_actions", ThreadQuickActionsContent)
