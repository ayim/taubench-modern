import re
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Dict, Optional

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


class ActionServerExitedError(RuntimeError):
    pass


class ActionServerProcess:
    SHOW_OUTPUT = True

    def __init__(self, datadir: Path, executable_path: Path | None = None) -> None:
        from io import StringIO

        self._datadir = datadir.absolute()
        self._process: Optional["Process"] = None
        self._host: str = ""
        self._port: int = -1
        self.started: bool = False
        self._stdout = StringIO()
        self._stderr = StringIO()
        self._executable_path = (
            str(executable_path.absolute()) if executable_path else None
        )

    @property
    def datadir(self) -> Path:
        return self._datadir

    @property
    def host(self) -> str:
        if not self.started:
            raise RuntimeError(
                "The action server was not properly started (no host available)"
            )

        assert (
            self._host
        ), "The action server was not properly started (no host available)"
        return self._host

    @property
    def port(self) -> int:
        if not self.started:
            raise RuntimeError(
                "The action server was not properly started (no port available)"
            )

        assert (
            self._port > 0
        ), "The action server was not properly started (no port available)"
        return self._port

    @property
    def process(self) -> "Process":
        assert (
            self._process is not None
        ), "The action server was not properly started (process is None)."
        return self._process

    def start(
        self,
        *,
        logs_dir: Path,
        timeout: int = 500,
        db_file="db.sqlite",  # Could be `:memory:` for in-memory database
        actions_sync=True,
        cwd: Optional[Path | str] = None,
        add_shutdown_api: bool = False,
        min_processes: int = 0,
        max_processes: int = 20,
        reuse_processes: bool = False,
        lint: bool = False,
        additional_args: Optional[list[str]] = None,
        env: Optional[Dict[str, str]] = None,
        port=0,
        verbose="-v",
        use_https: bool = False,
    ) -> None:
        from sema4ai.common.process import Process

        if self.started:
            raise RuntimeError("The action process was already started.")

        self.started = True
        from concurrent.futures import Future

        if actions_sync:
            assert cwd, "cwd must be passed when synchronizing the actions."

        base_args: list[str]
        if self._executable_path:
            base_args = [self._executable_path]
        elif is_frozen():
            base_args = [sys.executable]
        else:
            base_args = [
                sys.executable,
                "-m",
                "sema4ai.action_server",
            ]
        new_args = base_args + [
            "start",
            "--actions-sync=false" if not actions_sync else "--actions-sync=true",
            f"--port={port}",
            f"--datadir={str(self._datadir)}",
            f"--db-file={db_file}",
        ]

        if verbose:
            new_args.append(verbose)

        if use_https:
            new_args.append("--https")

        if not lint:
            new_args.append("--skip-lint")

        new_args.append(f"--min-processes={min_processes}")
        new_args.append(f"--max-processes={max_processes}")
        if reuse_processes:
            new_args.append("--reuse-processes")

        if additional_args:
            new_args = new_args + additional_args

        use_env: Dict[str, str] = {}
        if add_shutdown_api:
            use_env["RC_ADD_SHUTDOWN_API"] = "1"
        if env:
            use_env.update(env)
        process = self._process = Process(new_args, cwd=cwd, env=use_env)

        if use_https:
            compiled = re.compile(r"Local Action Server: https://([\w.-]+):(\d+)")
        else:
            compiled = re.compile(r"Local Action Server: http://([\w.-]+):(\d+)")
        future: Future[tuple[str, str]] = Future()

        def collect_port_from_stdout(line):
            # Note: this is called in a thread.
            matches = re.findall(compiled, line)

            if matches:
                host, port = matches[0]
                future.set_result((host, port))

        stdout_file = logs_dir / "stdout.log"
        stderr_file = logs_dir / "stderr.log"

        def on_stdout(line):
            # Append text to stdout file
            with stdout_file.open("a+") as f:
                f.write(line)

            self._stdout.write(line)
            if self.SHOW_OUTPUT:
                sys.stdout.write(f"stdout: {line.rstrip()}\n")

        def on_stderr(line):
            with stderr_file.open("a+") as f:
                f.write(line)

            self._stderr.write(line)
            # Note: this is called in a thread.
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
                    except TimeoutError:
                        if is_debugger_active():
                            continue
                        if time.monotonic() - initial_time >= timeout:
                            raise TimeoutError()
                        if not process.is_alive():
                            raise ActionServerExitedError(
                                f"The process already exited with returncode: "
                                f"{process.returncode}\n"
                                f"Args: {new_args}"
                            )
            else:
                host, port = future.result(timeout)
        assert host
        self._host = host
        assert int(port) > 0, f"Expected port to be > 0. Found: {port}"
        self._port = int(port)

    def stop(self):
        """
        Returns a tuple with stdout/stderr.
        """
        if self._process is not None:
            self._process.stop()
            self._process = None

    def get_stdout(self):
        return self._stdout.getvalue()

    def get_stderr(self):
        return self._stderr.getvalue()
