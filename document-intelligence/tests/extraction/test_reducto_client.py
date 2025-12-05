import http.server
import socketserver
import threading

from reducto.types.shared import ParseResponse
from reducto.types.shared.bounding_box import BoundingBox
from reducto.types.shared.parse_response import (
    ResultFullResult,
    ResultFullResultChunk,
    ResultFullResultChunkBlock,
    ResultURLResult,
)
from reducto.types.shared.parse_usage import ParseUsage

from sema4ai_docint.extraction.reducto import SyncExtractionClient


def test_use_array_extract():
    # Cases which should use array_extract
    positive = [
        {
            "type": "object",
            "properties": {
                "totalAmount": {
                    "type": "number",
                    "description": (
                        "Total amount of the invoice, can be found at the bottom "
                        "follow by Grand Total - Net Payable"
                    ),
                },
                "lineItems": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "amount": {
                                "type": "number",
                                "description": "amount of the line item transaction",
                            }
                        },
                    },
                },
            },
            "required": ["totalAmount", "lineItems"],
        },
    ]

    # Cases which should not use array_extract
    negative = [
        {},
        {
            "type": "object",
            "properties": {
                "totalAmount": {
                    "type": "number",
                    "description": (
                        "Total amount of the invoice, can be found at the bottom "
                        "follow by Grand Total - Net Payable"
                    ),
                },
            },
            "required": ["totalAmount"],
        },
        {
            "type": "object",
            "properties": {
                "totalAmount": {
                    "type": "number",
                    "description": (
                        "Total amount of the invoice, can be found at the bottom "
                        "follow by Grand Total - Net Payable"
                    ),
                },
                # an array but not at the top-level
                "tables": {
                    "type": "object",
                    "properties": {
                        "buys": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "amount": {
                                        "type": "number",
                                        "description": "amount of the line item transaction",
                                    }
                                },
                            },
                        },
                        "sells": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "amount": {
                                        "type": "number",
                                        "description": "amount of the line item transaction",
                                    }
                                },
                            },
                        },
                    },
                    "required": ["buys", "sells"],
                },
            },
            "required": ["totalAmount", "tables"],
        },
    ]

    for schema in positive:
        assert SyncExtractionClient._has_top_level_array(schema) is True, (
            f"Expected array_extract=true for schema: {schema}"
        )

    for schema in negative:
        assert SyncExtractionClient._has_top_level_array(schema) is False, (
            f"Expected array_extract=false for schema: {schema}"
        )


def test_localize_parse_response():
    """Test fetching results from a URL endpoint."""

    # Create a simple HTTP server that returns a JSON response
    class TestHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()

            resp = ResultFullResult(
                type="full",
                chunks=[
                    ResultFullResultChunk(
                        content="chunk 1",
                        blocks=[
                            ResultFullResultChunkBlock(
                                bbox=BoundingBox(
                                    height=100,
                                    left=0,
                                    page=1,
                                    top=0,
                                    width=100,
                                ),
                                content="chunk 1 block 1",
                                type="Text",
                            )
                        ],
                        embed="",
                        enriched="",
                        enrichment_success=True,
                    ),
                    ResultFullResultChunk(
                        content="chunk 2",
                        blocks=[
                            ResultFullResultChunkBlock(
                                bbox=BoundingBox(
                                    height=100,
                                    left=0,
                                    page=1,
                                    top=0,
                                    width=100,
                                ),
                                content="block 1",
                                type="Text",
                            )
                        ],
                        embed="",
                        enriched="",
                        enrichment_success=True,
                    ),
                ],
            )
            resp = resp.model_dump_json()
            self.wfile.write(resp.encode())

    # Start server in a separate thread
    server = socketserver.TCPServer(("", 0), TestHandler)
    port = server.server_address[1]
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    try:
        # Test fetching from the test server
        resp = SyncExtractionClient.localize_parse_response(
            ParseResponse(
                result=ResultURLResult(
                    url=f"http://localhost:{port}",
                    result_id="test-result-id",
                    type="url",
                ),
                duration=0.0,
                job_id="test-job-id",
                usage=ParseUsage(
                    num_pages=1,
                ),
            )
        )

        # Verify that the result came from our test HTTP server
        assert resp
        result = resp.result
        assert result.type == "full"
        assert len(result.chunks) == 2
        assert result.chunks[0].content == "chunk 1"
        assert result.chunks[1].content == "chunk 2"
    finally:
        # Shut down the test server
        server.shutdown()
        server.server_close()
