#!/usr/bin/env python3
"""
Standalone webhook receiver for testing Sema4AI work item callbacks.

Usage:
    uv run webhook_receiver.py
    uv run webhook_receiver.py --secret your-secret-key
"""

import argparse
import hashlib
import hmac
import json
import logging
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class WebhookHandler(BaseHTTPRequestHandler):
    """HTTP request handler for webhook requests."""

    def __init__(self, *args, secret: str | None = None, **kwargs):
        self.secret = secret
        super().__init__(*args, **kwargs)

    def do_POST(self):  # noqa: N802
        """Handle POST requests (webhooks)."""
        try:
            # Read the request body
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)

            # Parse JSON body
            try:
                webhook_data = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in webhook body: {e}")
                self.send_error(400, "Invalid JSON")
                return

            # Verify signature if secret is provided
            if self.secret:
                signature_header = self.headers.get("X-SEMA4AI-SIGNATURE")
                if not signature_header:
                    logger.error("Missing X-SEMA4AI-SIGNATURE header")
                    self.send_error(401, "Missing signature")
                    return

                expected_signature = self._compute_signature(self.secret, webhook_data)
                if not hmac.compare_digest(signature_header, expected_signature):
                    logger.error("Invalid signature")
                    self.send_error(401, "Invalid signature")
                    return

                logger.info("✅ Signature verified successfully")

            # Print webhook details
            self._print_webhook(webhook_data)

            # Send success response
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response = {"status": "received", "timestamp": datetime.now().isoformat()}
            self.wfile.write(json.dumps(response).encode("utf-8"))

        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            self.send_error(500, "Internal server error")

    def do_GET(self):  # noqa: N802
        """Handle GET requests (health check)."""
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Webhook receiver is running")

    def _compute_signature(self, secret: str, body: dict) -> str:
        """Computes a signature (SHA-256) for the body using the same method as callbacks.py."""
        # Use sort_keys=True and separators for consistent JSON serialization
        body_json = json.dumps(body, sort_keys=True, separators=(",", ":"))
        return hmac.new(secret.encode(), body_json.encode(), hashlib.sha256).hexdigest()

    def _print_webhook(self, webhook_data: dict):
        """Print webhook data in a readable format."""
        print("\n" + "=" * 80)
        print(f"🔔 WEBHOOK RECEIVED at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)

        # Print headers
        print("📋 HEADERS:")
        for header, value in self.headers.items():
            print(f"  {header}: {value}")

        print("\n📦 PAYLOAD:")
        print(json.dumps(webhook_data, indent=2))

        # Print key information prominently
        print("\n🔑 KEY INFORMATION:")
        print(f"  Work Item ID: {webhook_data.get('work_item_id', 'N/A')}")
        print(f"  Agent ID: {webhook_data.get('agent_id', 'N/A')}")
        print(f"  Thread ID: {webhook_data.get('thread_id', 'N/A')}")
        print(f"  Status: {webhook_data.get('status', 'N/A')}")
        print(f"  Work Item URL: {webhook_data.get('work_item_url', 'N/A')}")

        # Print recent messages
        recent_messages = webhook_data.get("recent_messages", [])
        if recent_messages:
            print(f"\n💬 RECENT MESSAGES ({len(recent_messages)}):")
            for i, message in enumerate(recent_messages, 1):
                print(f"  {i}. {message}")

        print("=" * 80)

    def log_message(self, f: str, *args):
        """Override to use our logger instead of stderr."""
        logger.info(f"{self.address_string()} - {f % args}")


def create_handler_class(secret: str | None = None):
    """Create a handler class with the secret baked in."""

    class Handler(WebhookHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, secret=secret, **kwargs)

    return Handler


def main():
    """Main function to run the webhook receiver."""
    parser = argparse.ArgumentParser(description="Webhook receiver for Sema4AI work item callbacks")
    parser.add_argument("--secret", type=str, help="Secret key for signature verification")
    parser.add_argument(
        "--port", type=int, default=44444, help="Port to listen on (default: 44444)"
    )
    parser.add_argument(
        "--host", type=str, default="localhost", help="Host to bind to (default: localhost)"
    )

    args = parser.parse_args()

    # Create handler class with secret
    handler_class = create_handler_class(args.secret)

    # Create and start server
    server = HTTPServer((args.host, args.port), handler_class)

    print(f"🚀 Webhook receiver starting on http://{args.host}:{args.port}")
    if args.secret:
        print("🔐 Signature verification is ENABLED")
    else:
        print("⚠️  Signature verification is DISABLED")

    print("\n📡 Webhook endpoint: POST /")
    print("🏥 Health check: GET /")
    print("\nPress Ctrl+C to stop the server")
    print("-" * 50)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n🛑 Server stopped by user")
        server.server_close()


if __name__ == "__main__":
    main()
