import json
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

SCHEMA_RESPONSE = json.dumps(
    {
        "type": "object",
        "title": "Invoice",
        "required": [
            "billed_to",
            "date_issued",
            "due_date",
            "invoice_number",
            "amount_due",
            "items",
            "total",
            "balance_due",
        ],
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": [
                        "description",
                        "rate",
                        "quantity",
                        "amount",
                    ],
                    "properties": {
                        "rate": {
                            "type": "string",
                            "description": "The rate per unit for the item or service.",
                        },
                        "amount": {
                            "type": "string",
                            "description": "The total amount for the given item or service.",
                        },
                        "quantity": {
                            "type": "string",
                            "description": "The quantity of the items or services billed.",
                        },
                        "description": {
                            "type": "string",
                            "description": "A brief description of the billed item or service.",
                        },
                    },
                },
                "description": "A list of items or services billed in the invoice.",
            },
            "total": {
                "type": "string",
                "description": "The total amount including taxes and additional fees, "
                "e.g., '$17,250.00'.",
            },
            "due_date": {
                "type": "string",
                "description": "The date by which payment is due, e.g., 'September 19, 2025'.",
            },
            "billed_to": {
                "type": "string",
                "description": "The name and address of the entity being billed.",
            },
            "amount_due": {
                "type": "string",
                "description": "The total amount due on the invoice, e.g., '$17,250.00'.",
            },
            "balance_due": {
                "type": "string",
                "description": "The remaining balance due, e.g., '$17,250.00'.",
            },
            "date_issued": {
                "type": "string",
                "description": "The date the invoice was issued in a string format, "
                "e.g., 'August 20, 2025'.",
            },
            "invoice_number": {
                "type": "string",
                "description": "The unique identifier for the invoice, e.g., 'INV-00001'.",
            },
        },
        "description": "A schema representing an invoice document.",
    },
    indent=2,
)


# TODO: Fix lint issues in this function
def _create_agent_dummy_server_class(responses):  # noqa: C901
    """Factory function to create a request handler class with specific responses."""

    class _AgentDummyServer(BaseHTTPRequestHandler):
        def __init__(self, request, client_address, server):
            self.responses = responses or []
            self.server_instance = server._server_instance
            super().__init__(request, client_address, server)

        def _send_response(self, status_code=200, headers=None, body=None):
            self.send_response(status_code)
            if headers:
                for key, value in headers.items():
                    self.send_header(key, value)
            self.end_headers()
            if body:
                if isinstance(body, str):
                    self.wfile.write(body.encode("utf-8"))
                else:
                    self.wfile.write(json.dumps(body).encode("utf-8"))

        def do_GET(self):  # noqa: N802, RUF100
            parsed_path = urllib.parse.urlparse(self.path)

            # Handle /api/v2/ok endpoint for URL accessibility check
            if "/api/v2/ok" in parsed_path.path:
                self._send_response(
                    200,
                    headers={"Content-Type": "application/json"},
                    body={"status": "ok"},
                )
                return
            else:
                self._send_response(
                    404,
                    headers={"Content-Type": "application/json"},
                    body={"error": "Not Found"},
                )
                return

        def do_POST(self):  # noqa: N802, RUF100
            parsed_path = urllib.parse.urlparse(self.path)

            content_length = int(self.headers.get("Content-Length", 0))
            post_data = self.rfile.read(content_length)

            try:
                request_body = json.loads(post_data)
            except json.JSONDecodeError:
                self._send_response(
                    400,
                    headers={"Content-Type": "application/json"},
                    body={"error": "Invalid JSON"},
                )
                return

            if "/api/v2/prompts/generate" in parsed_path.path:
                # Extract query parameters
                query_params = urllib.parse.parse_qs(parsed_path.query)
                thread_id = query_params.get("thread_id", [None])[0]
                agent_id = query_params.get("agent_id", [None])[0]

                # Store the request for testing
                self.server_instance.last_request = {
                    "body": request_body,
                    "thread_id": thread_id,
                    "agent_id": agent_id,
                    "path": self.path,  # Store the full request path
                }

                # Get response from queue
                if self.responses:
                    user_response = self.responses.pop(0)
                else:
                    user_response = "Request processed successfully."

                # Return the expected response format
                response = {
                    "content": [
                        {
                            "kind": "text",
                            "text": user_response,
                        }
                    ],
                    "role": "agent",
                    "raw_response": None,
                    "stop_reason": None,
                    "usage": {
                        "input_tokens": 115,
                        "output_tokens": len(str(user_response).split()),
                        "total_tokens": 115 + len(str(user_response).split()),
                    },
                    "metrics": {},
                    "metadata": {},
                    "additional_response_fields": {},
                }

                self._send_response(
                    200, headers={"Content-Type": "application/json"}, body=response
                )
                return
            else:
                self._send_response(
                    404,
                    headers={"Content-Type": "application/json"},
                    body={"error": "Not Found"},
                )
                return

    return _AgentDummyServer


class AgentDummyServer:
    def __init__(self, responses=None):
        """
        Initialize the dummy server with a queue of responses.

        Args:
            responses: List of responses to return in order. Each POST request
                      will pop the next response from this list.
        """
        self.server = None
        self.thread = None
        self.port = None
        self.last_request = None
        self.responses = responses or []

    def _start_in_thread(self):
        # Use port 0 to let the OS assign a free port (like files_dummy_server.py)
        handler_class = _create_agent_dummy_server_class(self.responses)
        self.server = HTTPServer(("localhost", 0), handler_class)
        self.server._server_instance = self  # Store reference to self
        self.port = self.server.server_port

        self.server.serve_forever()

    def start(self):
        self.thread = Thread(target=self._start_in_thread, daemon=True)
        self.thread.start()
        # Give the server a moment to start
        time.sleep(0.1)

    def get_port(self):
        return self.port

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.thread:
            self.thread.join(timeout=1)
