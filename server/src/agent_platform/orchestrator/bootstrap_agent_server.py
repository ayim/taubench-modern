import os
import sys
from pathlib import Path

from agent_platform.orchestrator.bootstrap_base import (
    BootstrapBase,
    ProcessExitedError,
    Stream,
    is_frozen,
)

AgentServerExitedError = ProcessExitedError


class AgentServerProcess(BootstrapBase):
    """
    Class to start and stop the agent server.
    """

    _name = "agent_server"

    # The line we want to match is something as:
    # 'INFO:     Uvicorn running on http://127.0.0.1:51980 (Press CTRL+C to quit)\r\n'
    # We want to extract the host and port from this line.
    REGEXP_TO_MATCH_HOST_PORT = r".*running on http://([\w.-]+):(\d+)\s.*"

    # The line we want to match for application startup:
    # 'INFO:     Application startup complete.'
    REGEXP_TO_MATCH_APP_START = r".*Application startup complete.*"

    def __init__(self, datadir: Path, executable_path: Path | None = None) -> None:
        super().__init__(executable_path)
        self._datadir = datadir.absolute()

    @property
    def datadir(self) -> Path:
        return self._datadir

    def get_base_args(self) -> list[str]:
        """
        Returns the base arguments to start the agent server (may be overridden by
        subclasses).
        """
        # Allow the `SEMA4AI_TEST_AGENT_SERVER_EXECUTABLE` to be set in the environment
        # (to test a built version of the agent server).
        test_agent_server_executable = os.environ.get("SEMA4AI_TEST_AGENT_SERVER_EXECUTABLE")
        base_args: list[str]
        common_args = ["--ignore-config"]
        if test_agent_server_executable:
            if not os.path.exists(test_agent_server_executable):
                if sys.platform == "win32" and not test_agent_server_executable.endswith(".exe"):
                    test_agent_server_executable = test_agent_server_executable + ".exe"
                    if not os.path.exists(test_agent_server_executable):
                        raise FileNotFoundError(
                            "The test agent server executable "
                            f"{os.path.abspath(test_agent_server_executable)} does not exist."
                        )
                else:
                    raise FileNotFoundError(
                        "The test agent server executable "
                        f"{os.path.abspath(test_agent_server_executable)} does not exist."
                    )
            base_args = [test_agent_server_executable]
        elif self._executable_path:
            base_args = [self._executable_path]
        elif is_frozen():
            base_args = [sys.executable, *common_args]
        else:
            base_args = [
                sys.executable,
                "-m",
                "agent_platform.server",
                *common_args,
            ]

        return base_args

    def start(
        self,
        *,
        logs_dir: Path,
        timeout: int = 30,
        cwd: Path | str | None = None,
        additional_args: list[str] | None = None,
        env: dict[str, str] | None = None,
        port=0,
    ) -> None:
        from sema4ai.common.process import Process

        if self.started:
            raise RuntimeError("The agent server process was already started.")

        base_args = self.get_base_args()
        new_args = [
            *base_args,
            "--host=127.0.0.1",
            f"--port={port}",
            "--data-dir",
            str(self._datadir),
            "--log-dir",
            str(logs_dir),
        ]

        if additional_args:
            new_args = new_args + additional_args

        use_env: dict[str, str] = {}
        if env:
            use_env.update(env)

        process = self._process = Process(new_args, cwd=cwd, env=use_env)

        # Setup output files
        self.setup_output_files(process, logs_dir)

        # Register callbacks before starting the process
        # Both port detection and application startup can appear in either stdout or stderr
        self.register_port_precondition(self.REGEXP_TO_MATCH_HOST_PORT, Stream.BOTH)
        self.register_application_start_precondition(self.REGEXP_TO_MATCH_APP_START, Stream.BOTH)

        # Start the process and wait for all callbacks
        self.start_process_and_wait_for_preconditions(process, timeout)
