"""Module provided for backwards compatibility with Studio 1.2.5."""

import asyncio
import multiprocessing

# from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ServerInfo:
    """
    Information about the running server instances collected from the
    server's PID file after writing.
    """

    host: str
    port: int
    base_url: str
    pid: int


class AgentServerManager:
    """Async context manager for managing the Agent Server."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        data_dir: Path | None = None,
    ) -> None:
        self.host = host
        self.port = port
        self.data_dir = data_dir
        self.process: multiprocessing.Process | None = None
        self.server_info: ServerInfo | None = None

    def _start_server_process(self) -> None:
        """Start the server in a separate process."""
        from agent_platform.server.main import main

        args = ["--host", self.host, "--port", str(self.port)]
        if self.data_dir:
            args.extend(["--data-dir", str(self.data_dir)])

        self.process = multiprocessing.Process(
            target=main,
            args=(args,),
        )
        self.process.start()

    async def _wait_for_server(self, timeout: float = 10.0) -> ServerInfo:
        """Wait for server to start and return server info."""
        start_time = asyncio.get_event_loop().time()
        while True:
            if asyncio.get_event_loop().time() - start_time > timeout:
                raise TimeoutError("Server failed to start within timeout")

            try:
                # Try to read the PID file to get server info
                pid_file = (self.data_dir or Path.cwd()) / "agent-server.pid"
                if pid_file.exists():
                    import json

                    data = json.loads(pid_file.read_text())
                    return ServerInfo(**data)
            except Exception:
                pass

            await asyncio.sleep(0.1)

    # @asynccontextmanager
    # async def start(self) -> AgentClient:
    #     """Start the server and yield a client instance."""
    #     try:
    #         self._start_server_process()
    #         self.server_info = await self._wait_for_server()

    #         # Create and yield the client
    #         client = AgentClient(self.server_info.base_url)
    #         yield client

    #     finally:
    #         # Cleanup when context exits
    #         if self.process is not None:
    #             self.process.terminate()
    #             self.process.join()
    #             self.process = None


if __name__ == "__main__":
    from agent_platform.server.main import main

    main()
