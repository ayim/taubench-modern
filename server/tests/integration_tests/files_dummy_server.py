import json
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path


class _SimpleFileServer(BaseHTTPRequestHandler):
    def __init__(self, files_path: Path, server: "FilesDummyServer", *args, **kwargs):
        self.files_path = files_path
        self.files_path.mkdir(parents=True, exist_ok=True)
        self._server = server
        super().__init__(*args, **kwargs)

    def _send_response(self, status_code=200, headers=None, body=None):
        self.send_response(status_code)
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)
        self.end_headers()
        if body:
            self.wfile.write(body.encode("utf-8"))

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path_parts = parsed_path.path.split("/")[1:]

        if len(path_parts) == 1 and path_parts[0] == "":
            # Get the presigned get url
            url = f"http://localhost:{self._server.get_port()}/presigned-url"
            self._send_response(
                200,
                headers={"Content-Type": "application/json"},
                body=json.dumps({"url": url}),
            )
            return

        if len(path_parts) == 1 and path_parts[0] == "presigned-url":
            self._send_response(
                200,
                headers={"Content-Type": "application/json"},
                body=json.dumps("the file contents"),
            )
            return

        self._send_response(
            404,
            headers={"Content-Type": "application/json"},
            body=json.dumps({"error": "Not Found"}),
        )

    def do_POST(self):
        import sema4ai_http

        parsed_path = urllib.parse.urlparse(self.path)
        path_parts = parsed_path.path.split("/")[1:]

        content_length = int(self.headers.get("Content-Length", 0))
        content_type = self.headers.get("Content-Type")
        post_data = self.rfile.read(content_length)
        if (
            post_data
            and content_type
            not in [
                "application/octet-stream",
            ]
            and not content_type.startswith("multipart/form-data")
        ):
            try:
                request_body = json.loads(post_data)
            except json.JSONDecodeError:
                self._send_response(
                    400,
                    headers={"Content-Type": "application/json"},
                    body=json.dumps({"error": "Invalid JSON"}),
                )
                return
        else:
            request_body = {}

        if len(path_parts) == 1 and path_parts[0] == "presigned-url":
            assert content_type in [
                "application/octet-stream",
            ] or content_type.startswith("multipart/form-data")
            self._send_response(200, headers={"Content-Type": "application/json"})
            return

        if len(path_parts) == 1 and path_parts[0] == "":
            # this is the 'get presigned post url'
            url = f"http://localhost:{self._server.get_port()}/presigned-url"
            response_body = json.dumps(
                {
                    "url": url,
                    "form_data": {
                        "fileId": request_body["fileId"],
                        "expiresIn": request_body["expiresIn"],
                    },
                }
            )
            self._send_response(
                200,
                headers={"Content-Type": "application/json"},
                body=response_body,
            )
            return

        self._send_response(
            404,
            headers={"Content-Type": "application/json"},
            body=json.dumps({"error": "Not Found"}),
        )


class FilesDummyServer:
    def __init__(self, files_path: Path):
        self.files_path = files_path

    def _start_in_thread(self, files_path: Path):
        import threading

        port = 0
        server_address = ("", port)
        httpd = HTTPServer(
            server_address,
            lambda *args, **kwargs: _SimpleFileServer(
                files_path, self, *args, **kwargs
            ),
        )
        print(f"Starting server on port `{httpd.server_port}`")
        thread = threading.Thread(target=httpd.serve_forever)
        thread.start()
        return httpd

    def start(self):
        self.httpd = self._start_in_thread(self.files_path)

    def get_port(self):
        return self.httpd.server_port

    def stop(self):
        self.httpd.shutdown()
