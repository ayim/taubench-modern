import sys
from pathlib import Path

from agent_platform.orchestrator.bootstrap_base import (
    BootstrapBase,
    ProcessExitedError,
    Stream,
    is_frozen,
)

ActionServerExitedError = ProcessExitedError  # Alias for backward compatibility


class ActionServerProcess(BootstrapBase):
    _name = "action_server"

    # The line we want to match is something like:
    # 'Local Action Server: http://127.0.0.1:12345'
    # or 'Local Action Server: https://127.0.0.1:12345'
    REGEXP_TO_MATCH_HOST_PORT_HTTP = r"Local Action Server: http://([\w.-]+):(\d+)"
    REGEXP_TO_MATCH_HOST_PORT_HTTPS = r"Local Action Server: https://([\w.-]+):(\d+)"

    # Application startup pattern could be added here if needed
    # REGEXP_TO_MATCH_APP_START = r".*Application startup complete.*"

    def __init__(self, datadir: Path, executable_path: Path | None = None) -> None:
        BootstrapBase.__init__(self, executable_path)

        self._datadir = datadir.absolute()

    @property
    def datadir(self) -> Path:
        return self._datadir

    def import_action_package(self, action_package_path: Path, *, logs_dir: Path, db_file: str = "db.sqlite") -> None:
        import os

        from sema4ai.common.process import Process

        assert os.path.isabs(action_package_path), f"Action package path must be absolute: {action_package_path}"
        assert action_package_path.exists(), f"Action package path does not exist: {action_package_path}"

        args = self._get_base_args()
        args.append("import")
        args.append(f"--dir={action_package_path.as_posix()}")
        args.append(f"--datadir={self._datadir.as_posix()}")
        args.append(f"--db-file={db_file}")
        process = Process(args)

        stdout_file = logs_dir / "action-server-import-stdout.log"
        stderr_file = logs_dir / "action-server-import-stderr.log"

        def on_stdout(line):
            # Append text to stdout file
            with stdout_file.open("a+b") as f:
                f.write(line.encode("utf-8", "replace"))

            self._stdout.write(line)
            if self.SHOW_OUTPUT:
                sys.stdout.write(f"stdout: {line.rstrip()}\n")

        def on_stderr(line):
            with stderr_file.open("a+b") as f:
                f.write(line.encode("utf-8", "replace"))

            self._stderr.write(line)
            # Note: this is called in a thread.
            sys.stderr.write(f"stderr: {line.rstrip()}\n")

        process.on_stderr.register(on_stderr)
        process.on_stdout.register(on_stdout)

        process.start()
        process.join()
        if process.returncode != 0:
            raise RuntimeError(
                f"Failed to import action package: {action_package_path}\n"
                f"Stderr: {self._stderr.getvalue()}\n"
                f"Stdout: {self._stdout.getvalue()}\n"
            )

    def _get_base_args(self) -> list[str]:
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
        return base_args

    def start(
        self,
        *,
        logs_dir: Path,
        timeout: int = 30 * 60,  # Bootstrapping the env may be really slow
        db_file="db.sqlite",  # Could be `:memory:` for in-memory database
        actions_sync=True,
        cwd: Path | str | None = None,
        add_shutdown_api: bool = False,
        min_processes: int = 0,
        max_processes: int = 20,
        reuse_processes: bool = False,
        lint: bool = False,
        additional_args: list[str] | None = None,
        env: dict[str, str] | None = None,
        port=0,
        verbose="-v",
        use_https: bool = False,
        parent_pid: int | None = None,
    ) -> None:
        from sema4ai.common.process import Process

        if self.started:
            raise RuntimeError("The action process was already started.")

        if actions_sync:
            assert cwd, "cwd must be passed when synchronizing the actions."

        base_args = self._get_base_args()

        new_args = [
            *base_args,
            "start",
            "--actions-sync=false" if not actions_sync else "--actions-sync=true",
            f"--port={port}",
            f"--datadir={self._datadir.as_posix()}",
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

        if parent_pid is not None:
            new_args.append(f"--parent-pid={parent_pid}")

        if additional_args:
            new_args = new_args + additional_args

        use_env: dict[str, str] = {}
        if add_shutdown_api:
            use_env["RC_ADD_SHUTDOWN_API"] = "1"
        if env:
            use_env.update(env)
        process = self._process = Process(new_args, cwd=cwd, env=use_env)

        # Setup output files
        self.setup_output_files(process, logs_dir)

        # Register port callback with appropriate regex based on https setting
        match_host_port_regexp = (
            self.REGEXP_TO_MATCH_HOST_PORT_HTTPS if use_https else self.REGEXP_TO_MATCH_HOST_PORT_HTTP
        )
        self.register_port_precondition(match_host_port_regexp, Stream.BOTH)

        # Start the process and wait for all preconditions
        self.start_process_and_wait_for_preconditions(process, timeout)
