import logging
from dataclasses import dataclass, field
from typing import Any, Literal

from agent_platform.core.platforms.base import PlatformPrompt

logger = logging.getLogger(__name__)


DEFAULT_EXTRACT_SYSTEM_PROMPT = (
    "Be precise and thorough. Mark required, missing fields as null. Omit optional fields."
)


@dataclass(frozen=True)
class ExtractOptions:
    """Options for the extract operation."""

    extraction_schema: str | dict[str, Any] = field(
        metadata={
            "description": (
                "The JSONSchema which describes the desired extracted output from the file."
            )
        }
    )
    """The schema to use for the extract operation."""

    extraction_config: dict[str, Any] = field(
        default_factory=dict,
        metadata={"description": "Advanced Reducto configuration."},
    )
    """Advanced Reducto configuration."""

    start_page: int | None = field(
        default=None,
        metadata={"description": "The start page of the file to extract from."},
    )
    """The start page of the file to extract from."""

    end_page: int | None = field(
        default=None,
        metadata={"description": "The end page of the file to extract from."},
    )
    """The end page of the file to extract from."""


@dataclass(frozen=True)
class ParseOptions:
    """Options for the parse operation."""

    full_output: bool = field(
        default=False,
        metadata={
            "description": (
                "If True, returns complete document structure with coordinates, metadata, "
                "and job details (recommended for tables/complex documents). If False, "
                "returns only basic text content."
            )
        },
    )
    """If True, returns complete document structure."""

    force_reload: bool = field(
        default=False,
        metadata={"description": "Force a new parse even if the file has already been parsed."},
    )
    """Force a new parse even if the file has already been parsed."""


@dataclass(frozen=True)
class ReductoPrompt(PlatformPrompt):
    """A prompt for the Reducto platform."""

    operation: Literal["extract", "parse", "classify"] = field(
        metadata={
            "description": "The operation this prompt wishes to perform.",
        },
    )
    """The operation this prompt wishes to perform."""

    file_name: str = field(
        metadata={
            "description": "The name of the document to use for the operation.",
        },
    )
    """The name of the document to use for the operation."""

    system_prompt: str | None = field(
        default=None,
        metadata={
            "description": "A system prompt to use for the operation.",
        },
    )
    """A system prompt to use for the operation."""

    parse_options: ParseOptions | None = field(
        default=None,
        metadata={
            "description": "Options to use if this prompt is for a parse operation.",
        },
    )
    """Options to use if this prompt is for a parse operation."""

    extract_options: ExtractOptions | None = field(
        default=None,
        metadata={
            "description": "Options to use if this prompt is for an extract operation.",
        },
    )
    """Options to use if this prompt is for an extract operation."""

    def as_platform_request(
        self,
        model: str,
        stream: bool = False,
    ):
        """Here, for this client, we will have handling that's a little different.

        Instead of being able to neatly go "to a platform request", we need to
        the client will need to inspect the prompt a bit and choose what to do.

        For now, we will just return the prompt as is.
        """

        return ReductoPrompt(
            operation=self.operation,
            file_name=self.file_name,
            system_prompt=self.system_prompt,
        )
