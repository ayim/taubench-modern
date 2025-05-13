import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from reducto.types import ExtractRunParams, ParseRunParams

from agent_platform.core.platforms.base import PlatformPrompt

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReductoPrompt(PlatformPrompt):
    """A prompt for the Reducto platform."""

    operation: Literal["extract", "parse"] = field(
        metadata={
            "description": "The operation this prompt wishes to perform.",
        },
    )
    """The operation this prompt wishes to perform."""

    document_name: str = field(
        metadata={
            "description": "The name of the document to use for the operation.",
        },
    )
    """The name of the document to use for the operation."""

    document_bytes: bytes = field(
        metadata={
            "description": "The bytes of the document to use for the operation.",
        },
    )
    """The bytes of the document to use for the operation."""

    system_prompt: str | None = field(
        default=None,
        metadata={
            "description": "A system prompt to use for the operation.",
        },
    )
    """A system prompt to use for the operation."""

    parse_options: "ParseRunParams | None" = field(
        default=None,
        metadata={
            "description": "Options to use if this prompt is for a parse operation.",
        },
    )
    """Options to use if this prompt is for a parse operation."""

    extract_options: "ExtractRunParams | None" = field(
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
        from reducto.types import (
            ExtractRunParams,
            ParseRunParams,
        )
        from reducto.types.shared_params import (
            AdvancedProcessingOptions,
            BaseProcessingOptions,
            PageRange,
        )
        from reducto.types.shared_params.advanced_processing_options import (
            LargeTableChunking,
        )
        from reducto.types.shared_params.base_processing_options import (
            Chunking,
            FigureSummary,
            TableSummary,
        )

        parse_options = self.parse_options
        if self.operation == "parse" and parse_options is None:
            parse_options = ParseRunParams(
                document_url="unset",
                options=BaseProcessingOptions(
                    chunking=Chunking(
                        chunk_mode="section",
                    ),
                    table_summary=TableSummary(
                        enabled=True,
                    ),
                    figure_summary=FigureSummary(
                        enabled=True,
                    ),
                    filter_blocks=[
                        "Header",
                        "Footer",
                        "Page Number",
                        "Comment",
                    ],
                    force_url_result=False,
                ),
                advanced_options=AdvancedProcessingOptions(
                    ocr_system="highres",
                    table_output_format="html",
                    merge_tables=False,
                    continue_hierarchy=True,
                    keep_line_breaks=False,
                    page_range=PageRange(
                        start=None,
                        end=None,
                    ),
                    large_table_chunking=LargeTableChunking(
                        enabled=True,
                        size=50,
                    ),
                    spreadsheet_table_clustering="default",
                    remove_text_formatting=True,
                    filter_line_numbers=True,
                ),
                experimental_options={
                    # This might not be typeable always, as they
                    # could add things to the backend before updating
                    # the client library.
                    "enrich": {"enabled": False, "mode": "standard"},
                    "native_office_conversion": False,
                    "enable_checkboxes": False,
                    "rotate_pages": True,
                    "enable_underlines": False,
                    "enable_equations": False,
                    "return_figure_images": True,
                    "layout_enrichment": False,
                    "layout_model": "default",
                },
            )

        extract_options = self.extract_options
        if self.operation == "extract" and extract_options is None:
            extract_options = ExtractRunParams(
                document_url="unset",
                schema={},  # TODO: where from prompt do we get this?
                options=BaseProcessingOptions(
                    extraction_mode="ocr",
                    ocr_mode="standard",
                    chunking=Chunking(
                        chunk_mode="disabled",
                    ),
                    table_summary=TableSummary(
                        enabled=False,
                    ),
                    figure_summary=FigureSummary(
                        enabled=False,
                    ),
                    filter_blocks=[
                        "Header",
                        "Footer",
                        "Page Number",
                        "Comment",
                    ],
                    force_url_result=False,
                ),
                advanced_options=AdvancedProcessingOptions(
                    ocr_system="highres",
                    table_output_format="html",
                    merge_tables=False,
                    continue_hierarchy=True,
                    keep_line_breaks=False,
                    page_range=PageRange(
                        start=None,
                        end=None,
                    ),
                    large_table_chunking=LargeTableChunking(
                        enabled=True,
                        size=50,
                    ),
                    spreadsheet_table_clustering="default",
                    remove_text_formatting=False,
                    filter_line_numbers=False,
                ),
                experimental_options={
                    # This might not be typeable always, as they
                    # could add things to the backend before updating
                    # the client library.
                    "enrich": {"enabled": False, "mode": "standard"},
                    "native_office_conversion": False,
                    "enable_checkboxes": False,
                    "rotate_pages": True,
                    "enable_underlines": False,
                    "enable_equations": False,
                    "return_figure_images": False,
                    "layout_enrichment": False,
                    "layout_model": "default",
                },
            )

        return ReductoPrompt(
            operation=self.operation,
            document_name=self.document_name,
            document_bytes=self.document_bytes,
            system_prompt=self.system_prompt,
            parse_options=parse_options,
            extract_options=extract_options,
        )
