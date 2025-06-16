import threading

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse


class OAuthRedirectServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 8080):
        self.host = host
        self.port = port
        self._code: str | None = None
        self._server_thread = None
        self._app = FastAPI()
        self._shutdown_event = threading.Event()

        @self._app.get("/")
        async def handle_redirect(request: Request):
            code = request.query_params.get("code")
            if code:
                self._code = code
                self._shutdown_event.set()
                return PlainTextResponse("Authorization code received. You can close this window.")
            return PlainTextResponse("Missing 'code' in query parameters.", status_code=400)

    def _run_uvicorn(self):
        uvicorn.run(self._app, host=self.host, port=self.port, log_level="error")

    def wait_for_code(self, timeout: int | None = 300) -> str | None:
        self._server_thread = threading.Thread(target=self._run_uvicorn, daemon=True)
        self._server_thread.start()

        if self._shutdown_event.wait(timeout=timeout):
            return self._code
        return None
