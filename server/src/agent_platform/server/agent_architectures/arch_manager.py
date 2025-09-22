from pathlib import Path

from agent_platform.core.agent_architectures.architecture_info import ArchitectureInfo
from agent_platform.server.agent_architectures.base_runner import BaseAgentRunner
from agent_platform.server.agent_architectures.in_process_runner import (
    InProcessAgentRunner,
)


class AgentArchManager:
    def __init__(self, wheels_path: str, websocket_addr: str):
        self.wheels_path = Path(wheels_path)
        self.websocket_addr = websocket_addr
        # Cache of runners: (package,version,thread_id) -> runner
        self.active_runners: dict[tuple[str, str, str], BaseAgentRunner] = {}

        # A list of “trusted” or “builtin” packages that can run in-process:
        self.in_process_allowlist = {
            ("agent_platform.architectures.default", "*"),
            ("agent_platform.architectures.experimental_1", "*"),
            ("agent_platform.architectures.experimental_2", "*"),
            ("agent_platform.architectures.experimental_3", "*"),
        }

    def get_architectures(self) -> list[ArchitectureInfo]:
        in_process_architectures = InProcessAgentRunner.get_architectures()
        out_of_process_architectures = []  # TODO: someday
        return in_process_architectures + out_of_process_architectures

    async def get_runner(
        self,
        package_name: str,
        version: str,
        thread_id: str,
    ) -> BaseAgentRunner:
        """
        Return a runner object for the given CA + thread. If no runner exists,
        create it. Decide if it's in-process or out-of-process based on
        some logic.
        """
        key = (package_name, version, thread_id)
        if key in self.active_runners:
            return self.active_runners[key]

        # Decide if in-process or out-of-process
        in_process = (package_name, version) in self.in_process_allowlist or (
            package_name,
            "*",
        ) in self.in_process_allowlist
        if in_process:
            runner = InProcessAgentRunner(package_name, version, thread_id)
        else:
            # Out-of-process
            # We need to create (or find) the venv
            raise NotImplementedError("Out of process runner not implemented yet")

        self.active_runners[key] = runner
        return runner

    # async def _get_or_create_venv(self, package_name: str, version: str) -> Path:
    #     # Simplified example: create venv and install the wheel, etc.
    #     # Or you might keep a dictionary of (pkg,ver)->venv_path for caching.
    #     from subprocess import run

    #     import virtualenv

    #     venv_path = Path(f".venvs/{package_name}-{version}")
    #     if not venv_path.exists():
    #         # create it
    #         virtualenv.cli_run([str(venv_path)], program_name="virtualenv")
    #         # install the wheel
    #         wheel_path = self._find_wheel(package_name, version)
    #         pip_bin = (
    #             venv_path / ("Scripts" if sys.platform.startswith("win") else "bin")
    #             / "pip"
    #         )
    #         run([str(pip_bin), "install", str(wheel_path)], check=True)

    #     return venv_path

    def _find_wheel(self, package_name: str, version: str) -> Path:
        pattern = f"{package_name.replace('-', '_')}-{version}-*.whl"
        wheels = list(self.wheels_path.glob(pattern))
        if not wheels:
            raise ValueError(f"No wheel found for {package_name} version {version}")
        return wheels[0]

    async def cleanup_old_runners(self, max_age_seconds: int = 300):
        """
        If you need inactivity-based cleanup, you'd track last-used times in
        each runner or store them in a dict. Then kill them if
        they've been inactive too long.
        """
        pass
