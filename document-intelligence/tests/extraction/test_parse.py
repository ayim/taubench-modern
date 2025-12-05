import logging
from pathlib import Path
from typing import cast

import pytest
from reducto.types.shared.parse_response import ResultFullResult, ResultURLResult

from sema4ai_docint.extraction import SyncExtractionClient


class TestDocumentParse:
    logger: logging.Logger = logging.getLogger("sema4ai_docint.extraction")

    def _run_parsing_test(self, client: SyncExtractionClient, input_dir: str):
        """Helper method containing the common test logic"""
        # full path to the data.pdf file
        input_file = Path(__file__).parent / "test-data" / "parse" / input_dir / "data.pdf"

        # Upload
        uploaded_file_url = client.upload(input_file)

        # Parse
        parse_response = client.parse(uploaded_file_url)

        # Try to perform some basic validations
        # TODO we should come back in the future when we have a better expectation
        # around what the parse response should contain.
        assert parse_response.job_id, "Parse job ID should not be present"
        assert parse_response.pdf_url, "Parse PDF URL should not be present"

        if isinstance(parse_response.result, ResultFullResult):
            full_result = cast(ResultFullResult, parse_response.result)
            assert len(full_result.chunks) > 0, "Parse result should contain chunks"
        elif isinstance(parse_response.result, ResultURLResult):
            url_result = cast(ResultURLResult, parse_response.result)
            assert url_result.url, "Parse URL result should contain a URL"
        else:
            pytest.fail(f"Unexpected parse result type: {type(parse_response.result)}")

    def test_sanity_parsing(self, client: SyncExtractionClient):
        """Run a simple sanity check using anahau"""
        self._run_parsing_test(client, "sanity_using_ski_rental")
