from dataclasses import dataclass, field
from typing import Any, Self


@dataclass(frozen=True)
class ActionPackagePayload:
    name: str = field(
        metadata={
            "description": ("The name of the action package."),
        },
    )
    """The name of the action package."""

    description: str | None = field(
        default=None,
        metadata={
            "description": ("The description of the action package."),
        },
    )
    """The description of the action package."""

    action_package_url: str | None = field(
        default=None,
        metadata={
            "description": ("The URL of the action package."),
        },
    )
    """The URL of the action package."""

    action_package_base64: str | None = field(
        default=None,
        metadata={
            "description": ("The base64 encoded action package."),
        },
    )
    """The base64 encoded action package."""

    @classmethod
    def model_validate(cls, data: dict[str, Any]) -> Self:
        if isinstance(data, cls):
            return data

        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            action_package_url=data.get("action_package_url", ""),
            action_package_base64=data.get("action_package_base64", ""),
        )
