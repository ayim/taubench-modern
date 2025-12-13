from dataclasses import dataclass, field
from typing import Any, ClassVar


@dataclass
class ArchitectureInfo:
    """Information about an agent architecture."""

    PACKAGE_ATTRIBUTES_TO_ARCHITECTURE_INFO: ClassVar[dict[str, str]] = {
        "__author__": "author",
        "__summary__": "summary",
        "__license__": "license",
        "__copyright__": "copyright",
        "__built_in__": "built_in",
    }

    name: str = field(
        metadata={
            "description": "The name of the agent architecture.",
        },
    )
    """The name of the agent architecture."""
    built_in: bool = field(
        default=True,
        metadata={
            "description": "Whether the agent architecture is built-in.",
        },
    )
    """Whether the agent architecture is built-in."""
    version: str = field(
        default="0.0.1",
        metadata={
            "description": "The version of the agent architecture.",
        },
    )
    """The version of the agent architecture."""
    description: str | None = field(
        default=None,
        metadata={
            "description": "The description of the agent architecture.",
        },
    )
    """The description of the agent architecture."""
    author: str | None = field(
        default=None,
        metadata={
            "description": "The author of the agent architecture.",
        },
    )
    """The author of the agent architecture."""
    summary: str | None = field(
        default=None,
        metadata={
            "description": "The summary of the agent architecture.",
        },
    )
    """The summary of the agent architecture."""
    license: str | None = field(
        default=None,
        metadata={
            "description": "The license of the agent architecture.",
        },
    )
    """The license of the agent architecture."""
    copyright: str | None = field(
        default=None,
        metadata={
            "description": "The copyright of the agent architecture.",
        },
    )
    """The copyright of the agent architecture."""

    def model_dump(self) -> dict[str, str]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in self.__dict__.items() if v is not None}

    def model_dump_json(self) -> str:
        """Convert to JSON string, excluding None values."""
        from json import dumps

        return dumps(self.model_dump())

    @classmethod
    def model_validate(cls, data: dict[str, Any]) -> "ArchitectureInfo":
        """Validate and convert dictionary to ArchitectureInfo."""
        # We expect there to be a "name", "version", and "built_in" key
        if "name" not in data:
            raise ValueError("name is required")
        if "version" not in data:
            raise ValueError("version is required")
        if "built_in" not in data:
            raise ValueError("built_in is required")

        # Convert package attributes to ArchitectureInfo fields
        for attr, field_name in cls.PACKAGE_ATTRIBUTES_TO_ARCHITECTURE_INFO.items():
            if attr in data:
                data[field_name] = data[attr]
                del data[attr]

        return ArchitectureInfo(
            name=data["name"],
            built_in=(data["built_in"].lower() == "true" if isinstance(data["built_in"], str) else data["built_in"]),
            version=data["version"],
            description=data.get("description", "No description available."),
            author=data.get("author", "No author available."),
            summary=data.get("summary", "No summary available."),
            license=data.get("license", "No license available."),
            copyright=data.get("copyright", "No copyright available."),
        )
