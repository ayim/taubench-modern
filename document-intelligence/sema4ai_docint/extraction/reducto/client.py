"""
Main client implementation for doc-extraction.
"""

from itertools import chain
from typing import Any, ClassVar

import httpx
import sema4ai_http
from reducto.types import ExtractResponse, ParseResponse
from reducto.types.shared.parse_response import ResultFullResult

from sema4ai_docint.extraction.reducto.exceptions import (
    ExtractMultipleResultsError,
    ExtractNoResultsError,
)
from sema4ai_docint.logging import logger
from sema4ai_docint.models.extraction import ExtractionResult


class _BaseReductoClient:
    SEMA4_REDUCTO_ENDPOINT = "https://backend.sema4.ai/reducto"
    DEFAULT_EXTRACT_SYSTEM_PROMPT = (
        "Be precise and thorough. Mark required, missing fields as null. Omit optional fields."
    )

    _extract_only_keys: ClassVar[list[str]] = [
        "schema",
        "system_prompt",
        "generate_citations",
        "array_extract",
        "use_chunking",
        "include_images",
        "spreadsheet_agent",
        "agent_extract",
    ]

    @staticmethod
    def _make_mounts(
        network_config: sema4ai_http.NetworkProfile,
    ) -> dict[str, httpx.HTTPTransport | None]:
        """Make mounts for proxy configuration. Copied from sema4ai-http-helper README."""
        if not network_config.ssl_context:
            raise ValueError("SSL context missing from sema4ai-http-helper NetworkProfile")

        mounts: dict[str, httpx.HTTPTransport | None] = {}
        for http_proxy in chain(
            network_config.proxy_config.http, network_config.proxy_config.https
        ):
            mounts[http_proxy] = httpx.HTTPTransport(network_config.ssl_context)
        for no_proxy in network_config.proxy_config.no_proxy:
            mounts[no_proxy] = None

        return mounts

    @staticmethod
    def convert_extract_response(
        resp: ExtractResponse, prompt: str | None = None
    ) -> ExtractionResult:
        """Convert a Reducto ExtractResponse to a Sema4ai ExtractionResult.

        Note: in all our pipelines, we expect extraction chunking to be disabled, so
        we always only take the first result from Reducto ExtractResponse.
        """
        if len(resp.result) > 1:
            raise ExtractMultipleResultsError(results=resp.result, prompt=prompt)
        if not resp.result:
            raise ExtractNoResultsError(results=resp.result)

        # Extract citations if available. resp.citations is a list where each element
        # corresponds to citations for a chunk. We disable chunking, so we only use [0].
        citations = resp.citations[0] if (resp.citations and len(resp.citations) > 0) else None

        return ExtractionResult(
            results=resp.result[0],
            citations=citations,
            prompt=prompt,
        )

    @classmethod
    def _default_parse_opts(cls) -> dict[str, Any]:
        """
        Default parse options for Reducto.

        These options are shared across both parse and extract. Changes to this default option must
        be made with extreme care as they will affect the accuracy of extraction.
        """

        return {
            "options": {
                "extraction_mode": "ocr",
                "ocr_mode": "standard",
                "chunking": {"chunk_mode": "disabled"},
                "table_summary": {"enabled": False},
                "figure_summary": {"enabled": False},
                "filter_blocks": ["Page Number", "Header", "Footer", "Comment"],
                "force_url_result": False,
            },
            "advanced_options": {
                "ocr_system": "highres",
                "table_output_format": "html",
                "merge_tables": False,
                "continue_hierarchy": True,
                "keep_line_breaks": False,
                "page_range": {"start": None, "end": None},
                "large_table_chunking": {"enabled": True, "size": 50},
                "spreadsheet_table_clustering": "default",
                "remove_text_formatting": False,
                "filter_line_numbers": False,
            },
            "experimental_options": {
                "enrich": {"enabled": False, "mode": "standard"},
                "native_office_conversion": False,
                "enable_checkboxes": False,
                "rotate_pages": False,
                "enable_underlines": False,
                "enable_equations": False,
                "return_figure_images": False,
                "layout_enrichment": False,
                "layout_model": "default",
            },
            "timeout": 300,
        }

    def parse_opts(self, config: dict[str, Any] | None = None) -> dict[str, Any]:
        default_config = _BaseReductoClient._default_parse_opts()

        # Merge with provided configuration if available
        if config:
            # Some options are only valid for extract, not parse. We filter them out here.
            filtered_config = {
                k: v for k, v in config.items() if k not in _BaseReductoClient._extract_only_keys
            }
            return _BaseReductoClient.merge_config(default_config, filtered_config)

        return default_config

    def split_opts(self, config: dict[str, Any] | None = None) -> dict[str, Any]:
        """
        Constructs the default split options for Reducto, applying any overrides to the
        default configuration.
        """
        default_config = _BaseReductoClient._default_parse_opts()

        # Merge with provided configuration if available
        if config:
            return _BaseReductoClient.merge_config(default_config, config)

        return default_config

    def extract_opts(
        self,
        schema: dict[str, Any],
        system_prompt: str,
        start_page: int | None = None,
        end_page: int | None = None,
        extraction_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        default_config = _BaseReductoClient._default_parse_opts()

        # Merge in the extraction configuration with the default parse option
        default_config = _BaseReductoClient.merge_config(
            default_config,
            {
                "schema": schema,
                "advanced_options": {
                    "page_range": {
                        "start": start_page,
                        "end": end_page,
                    },
                },
                "array_extract": {
                    "enabled": False,
                    # Let the mode default to legacy, don't set it to streaming
                },
                "system_prompt": system_prompt,
                "generate_citations": True,
                "timeout": 300,
            },
        )

        # Merge with provided extraction configuration if available
        if extraction_config:
            actual_config = _BaseReductoClient.merge_config(default_config, extraction_config)
        else:
            actual_config = default_config

        # agent_extract is mutually exclusive with generate_citations. Disable citation generation
        # if agent_extract is enabled.
        if "agent_extract" in actual_config and actual_config["agent_extract"]["enabled"]:
            logger.info("Agent extract is enabled. Disabling citation generation.")
            actual_config["generate_citations"] = False

        return actual_config

    @classmethod
    def _has_top_level_array(cls, schema: dict[str, Any]) -> bool:
        """Check if the schema has a top-level property which is an array."""
        if "properties" in schema:
            for _, v in schema["properties"].items():
                if "type" in v and v["type"] == "array":
                    return True
        return False

    @classmethod
    def merge_config(
        cls, default_config: dict[str, Any], user_config: dict[str, Any] | None
    ) -> dict[str, Any]:
        """
        Merge user configuration with default configuration.

        Args:
            default_config: The default configuration from code
            user_config: The configuration from user (can be None)

        Returns:
            Merged configuration with database config overriding default config
        """
        if not user_config:
            return default_config

        def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
            """Recursively merge two dictionaries, with override taking precedence."""
            result = base.copy()
            for key, value in override.items():
                # Special handling for fields that should be completely replaced, not merged
                if key in ["schema", "system_prompt"]:
                    result[key] = value
                elif key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = deep_merge(result[key], value)
                else:
                    result[key] = value
            return result

        return deep_merge(default_config, user_config)

    @classmethod
    def localize_parse_response(cls, resp: ParseResponse) -> ParseResponse:
        """
        Conditionally fetch the remote results from a ResultURLResult in this ParseResponse.

        Args:
            resp: The ParseResponse to localize

        Returns:
            The parsed result as a ResultFullResult object
        """
        # Nothing to do, we have the full result
        if resp.result.type != "url":
            return resp

        try:
            response = sema4ai_http.get(resp.result.url)
            response.raise_for_status()  # Raise an exception for bad status codes
            result_dict = response.json()

            # Convert the dictionary to a ResultFullResult object
            resp.result = ResultFullResult(**result_dict)
            return resp
        except Exception as e:
            logger.error(f"Error fetching result from URL: {e!s}")
            raise e
