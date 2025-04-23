"""
Module with code to start the agent server and stop it.
"""

import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sema4ai.common.process import Process


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def is_debugger_active() -> bool:
    try:
        import pydevd  # type:ignore
    except ImportError:
        return False

    return bool(pydevd.get_global_debugger())


class AgentServerExitedError(RuntimeError):
    pass


class AgentServerProcess:
    """
    Class to start and stop the agent server.
    """

    SHOW_OUTPUT = False

    def __init__(self, datadir: Path) -> None:
        from io import StringIO

        self._datadir = datadir.absolute()
        self._process: Process | None = None
        self._host: str = ""
        self._port: int = -1
        self.started: bool = False
        self._stdout = StringIO()
        self._stderr = StringIO()

    @property
    def datadir(self) -> Path:
        return self._datadir

    @property
    def host(self) -> str:
        if not self.started:
            raise RuntimeError(
                "The agent server was not properly started (no host available)",
            )

        assert self._host, (
            "The agent server was not properly started (no host available)"
        )
        return self._host

    @property
    def port(self) -> int:
        if not self.started:
            raise RuntimeError(
                "The agent server was not properly started (no port available)",
            )

        assert self._port > 0, (
            "The agent server was not properly started (no port available)"
        )
        return self._port

    @property
    def process(self) -> "Process":
        assert self._process is not None, (
            "The agent server was not properly started (process is None)."
        )
        return self._process

    def start(  # noqa: C901, PLR0913, PLR0915
        self,
        *,
        logs_dir: Path,
        timeout: int = 25,
        cwd: Path | str | None = None,
        additional_args: list[str] | None = None,
        env: dict[str, str] | None = None,
        port: int | str = 0,
    ) -> None:
        import os
        import re
        import time

        from sema4ai.common.process import Process

        if self.started:
            raise RuntimeError("The agent server process was already started.")

        self.started = True
        from concurrent.futures import Future

        # Allow the `SEMA4AI_TEST_AGENT_SERVER_EXECUTABLE` to be set in the environment
        # (to test a built version of the agent server).
        test_agent_server_executable = os.environ.get(
            "SEMA4AI_TEST_AGENT_SERVER_EXECUTABLE",
        )
        if test_agent_server_executable:
            base_args = [test_agent_server_executable]
        else:
            base_args = [sys.executable, "-m", "agent_platform.server"]
        new_args = [
            *base_args,
            "--host=127.0.0.1",
            f"--port={port}",
        ]

        if additional_args:
            new_args = new_args + additional_args

        use_env: dict[str, str] = {}
        if env:
            use_env.update(env)
        use_env["SEMA4AI_STUDIO_HOME"] = str(self._datadir)
        use_env["SEMA4AI_STUDIO_LOG"] = str(logs_dir)

        process = self._process = Process(new_args, cwd=cwd, env=use_env)

        # The line we want to match is something as:
        # 'INFO:     Uvicorn running on http://127.0.0.1:51980
        # (Press CTRL+C to quit)\r\n'
        # We want to extract the host and port from this line.
        compiled = re.compile(r".*running on http://([\w.-]+):(\d+)\s.*")
        future: Future[tuple[str, str]] = Future()

        def collect_port_from_stdout(line: str) -> None:
            # Note: this is called in a thread.
            matches = re.findall(compiled, line)

            if matches:
                host, port = matches[0]
                future.set_result((host, port))

        stdout_file = logs_dir / "stdout.log"
        stderr_file = logs_dir / "stderr.log"

        def on_stdout(line: str) -> None:
            with stdout_file.open("a+") as f:
                f.write(line)

            self._stdout.write(line)
            if self.SHOW_OUTPUT:
                sys.stdout.write(f"stdout: {line.rstrip()}\n")

        def on_stderr(line: str) -> None:
            with stderr_file.open("a+") as f:
                f.write(line)

            self._stderr.write(line)
            # Note: this is called in a thread.
            if self.SHOW_OUTPUT:
                sys.stderr.write(f"stderr: {line.rstrip()}\n")

        process.on_stderr.register(on_stderr)
        process.on_stdout.register(on_stdout)

        with process.on_stderr.register(collect_port_from_stdout):
            process.start()
            if timeout > 1:
                initial_time = time.monotonic()
                while True:
                    try:
                        host, port = future.result(1)
                        break
                    except TimeoutError as e:
                        if is_debugger_active():
                            continue
                        if time.monotonic() - initial_time >= timeout:
                            raise TimeoutError() from e
                        if not process.is_alive():
                            raise AgentServerExitedError(
                                f"The process already exited with returncode: "
                                f"{process.returncode}\n"
                                f"Args: {new_args}",
                            ) from e
            else:
                host, port = future.result(timeout)
        assert host
        self._host = host
        assert int(port) > 0, f"Expected port to be > 0. Found: {port}"
        self._port = int(port)

    def stop(self) -> None:
        if self._process is not None:
            self._process.stop()
            self._process = None

    def get_stdout(self) -> str:
        return self._stdout.getvalue()

    def get_stderr(self) -> str:
        return self._stderr.getvalue()
