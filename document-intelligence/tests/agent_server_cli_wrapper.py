import logging
import threading
from pathlib import Path
from typing import TypedDict

log = logging.getLogger(__name__)


def get_release_artifact_relative_path(sys_platform: str, executable_name: str) -> str:
    """
    Helper function for getting the release artifact relative path as defined in S3 bucket.

    Args:
        sys_platform: Platform for which the release artifact is being retrieved.
        executable_name: Name of the executable we want to get the path for.
    """
    import platform

    machine = platform.machine()
    is_64 = not machine or "64" in machine

    if sys_platform == "win32":
        if is_64:
            return f"windows64/{executable_name}.exe"
        else:
            return f"windows32/{executable_name}.exe"

    elif sys_platform == "darwin":
        return f"macos_arm64/{executable_name}"

    elif is_64:
        return f"linux_x64/{executable_name}"
    else:
        return f"linux32/{executable_name}"


class ApiNamedTypedDict(TypedDict):
    host: str
    port: str


class LaunchJsonDataTypedDict(TypedDict):
    api: ApiNamedTypedDict
    isRunning: bool
    pid: int
    pidFilePath: str


class LaunchJsonTypedDict(TypedDict):
    success: bool
    data: LaunchJsonDataTypedDict


class AgentServerCliWrapper:
    VERSION = "v2.1.15"

    def __init__(self, tmpdir: Path) -> None:
        from typing import TYPE_CHECKING

        self.target = self.get_default_target()
        self._launch_json: LaunchJsonTypedDict | None = None
        self._tmpdir = tmpdir
        self._stdout_lines: list[str] = []
        self._stderr_lines: list[str] = []
        self._log_capture_threads: list[threading.Thread] = []
        if TYPE_CHECKING:
            # Type hint for http_connection if needed
            pass

    @property
    def launch_json(self) -> LaunchJsonTypedDict:
        if self._launch_json is None:
            raise RuntimeError("Agent server cli not started")
        return self._launch_json

    def get_default_target(self) -> Path:
        import os
        import sys

        if sys.platform == "win32":
            localappdata = os.environ.get("LOCALAPPDATA")
            if not localappdata:
                raise RuntimeError("Error. LOCALAPPDATA not defined in environment!")
            home = Path(localappdata) / "sema4ai"
        else:
            # Linux/Mac
            home = Path("~/.sema4ai").expanduser()

        directory = home / "agent-server-cli" / self.VERSION
        directory.mkdir(parents=True, exist_ok=True)
        executable_name = "agent-server"
        if sys.platform == "win32":
            executable_name += ".exe"
        ret = directory / executable_name
        return ret

    def download_agent_server_cli(self):
        if self.target.exists():
            return

        import sys

        relative_path = get_release_artifact_relative_path(sys.platform, "agent-server")
        url = f"https://cdn.sema4.ai/agent-server/{self.VERSION}/{relative_path}"
        import sema4ai_http

        try:
            result = sema4ai_http.download_with_resume(url, self.target, make_executable=True)
            assert result.status in (
                sema4ai_http.DownloadStatus.DONE,
                sema4ai_http.DownloadStatus.ALREADY_EXISTS,
            )
        except Exception as e:
            log.warning(f"Failed to download agent server from {url}: {e}")
            # Check if we have a local agent server binary
            if not self.target.exists():
                raise RuntimeError(
                    f"Agent server binary not found at {self.target} and download failed"
                ) from e

    def start(self):
        import json
        import os
        import subprocess
        import time

        log.info(f"Starting agent server at {self.target}")
        curtime = time.time()

        # Use port 9000 for agent server
        port = 9000

        # Set up environment variables
        env = os.environ.copy()

        # Set log directory if specified
        log_dir = env.get("SEMA4AI_AGENT_SERVER_LOG_DIR")
        if log_dir:
            env["SEMA4AI_AGENT_SERVER_LOG_DIR"] = log_dir
        else:
            # Default to the tmpdir for testing
            env["SEMA4AI_AGENT_SERVER_LOG_DIR"] = str(self._tmpdir)

        # Start the agent server process in background with port argument
        process = subprocess.Popen(
            [self.target, "--port", str(port)],
            cwd=self._tmpdir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
            # Don't wait for the process to complete
        )

        # Wait longer for the server to start and be ready
        time.sleep(5)

        # Check if process is still running
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            log.error(f"Agent server stdout: {stdout.decode('utf-8')}")
            log.error(f"Agent server stderr: {stderr.decode('utf-8')}")
            raise RuntimeError(f"Agent server failed to start: {stderr.decode('utf-8')}")

        log.info(f"Agent server process started with PID: {process.pid}")

        # Create a mock launch json similar to data server
        # Agent server doesn't provide a launch json, so we create one
        self._launch_json = {
            "success": True,
            "data": {
                "api": {"host": "127.0.0.1", "port": str(port)},
                "isRunning": True,
                "pid": process.pid,
                "pidFilePath": str(self._tmpdir / "agent-server.pid"),
            },
        }

        # Write PID file for agent server client to find
        with open(self._tmpdir / "agent-server.pid", "w") as f:
            json.dump({"base_url": f"http://127.0.0.1:{port}"}, f)

        log.info(f"Time taken: {time.time() - curtime} seconds")
        log.info(f"Agent server started with PID: {process.pid} on port {port}")

        # Store the process for later cleanup
        self._process = process

        # Start background threads to capture stdout and stderr
        self._start_log_capture(process)

    def get_http_port(self) -> int:
        return int(self.launch_json["data"]["api"]["port"])

    def _start_log_capture(self, process):
        """Start background threads to capture stdout and stderr from the agent server."""

        def capture_stdout():
            if process.stdout:
                for line in iter(process.stdout.readline, b""):
                    line_str = line.decode("utf-8").strip()
                    if line_str:
                        self._stdout_lines.append(line_str)
                        log.debug(f"Agent server stdout: {line_str}")
                process.stdout.close()

        def capture_stderr():
            if process.stderr:
                for line in iter(process.stderr.readline, b""):
                    line_str = line.decode("utf-8").strip()
                    if line_str:
                        self._stderr_lines.append(line_str)
                        log.debug(f"Agent server stderr: {line_str}")
                process.stderr.close()

        stdout_thread = threading.Thread(target=capture_stdout, daemon=True)
        stderr_thread = threading.Thread(target=capture_stderr, daemon=True)

        stdout_thread.start()
        stderr_thread.start()

        self._log_capture_threads = [stdout_thread, stderr_thread]

    def get_captured_logs(self) -> dict[str, list[str]]:
        """Get the captured stdout and stderr logs from the agent server."""
        return {
            "stdout": self._stdout_lines.copy(),
            "stderr": self._stderr_lines.copy(),
        }

    def get_log_file_path(self) -> Path | None:
        """Get the path to the agent server log file if it exists."""
        import os

        log_dir = os.environ.get("SEMA4AI_AGENT_SERVER_LOG_DIR", str(self._tmpdir))
        log_file = Path(log_dir) / "agent-server.log"

        if log_file.exists():
            return log_file
        return None

    def dump_logs_to_console(self):
        """Dump all captured logs to console for debugging."""
        logs = self.get_captured_logs()
        has_logs = False

        if logs["stdout"]:
            print("\n=== Agent Server STDOUT ===")
            for line in logs["stdout"]:
                print(line)
            has_logs = True

        if logs["stderr"]:
            print("\n=== Agent Server STDERR ===")
            for line in logs["stderr"]:
                print(line)
            has_logs = True

        # Also try to read from log file if it exists
        log_file = self.get_log_file_path()
        if log_file:
            try:
                print(f"\n=== Agent Server Log File ({log_file}) ===")
                print(log_file.read_text())
                has_logs = True
            except Exception as e:
                print(f"Failed to read log file {log_file}: {e}")

        # If no logs were captured, explain why
        if not has_logs:
            # Check if we're using an existing server
            if not hasattr(self, "_process"):
                print("\n=== No Agent Server Logs Available ===")
                print("Using existing agent server - logs not captured during test run.")
                print("To capture logs in future test runs:")
                print("1. Stop any existing agent server process")
                print("2. Set SEMA4AI_AGENT_SERVER_LOG_DIR environment variable (optional)")
                print("3. Let the test start a fresh agent server instance")
                print("\nTo view logs from the running server:")
                print("- Check the agent server's log output in its original terminal")
                print("- Look for log files in the server's working directory")
                print(f"- Check for logs in: {self._tmpdir}/agent-server.log")
            else:
                print("\n=== No Agent Server Logs Found ===")
                print("Agent server was started by test but no logs were captured.")
                print("This may indicate the server started but didn't produce output.")

    def _get_process_tree(self):
        """Get all processes in the process tree."""
        import psutil

        try:
            parent = psutil.Process(self._process.pid)
            children = parent.children(recursive=True)
            all_processes = [parent, *children]
            log.info(
                f"Found {len(all_processes)} processes to terminate "
                f"(parent + {len(children)} children)"
            )
            return all_processes
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            log.warning(f"Could not get process tree: {e}")
            return []

    def _terminate_process_gracefully(self):
        """Terminate the main process gracefully."""
        import time

        self._process.terminate()
        time.sleep(2)

        if self._process.poll() is None:
            log.info("Process still running after terminate, using kill")
            self._process.kill()
            time.sleep(1)

    def _cleanup_child_processes(self, all_processes):
        """Clean up any remaining child processes."""
        import time

        import psutil

        if not all_processes:
            return

        for proc in all_processes:
            try:
                if proc.is_running():
                    log.info(f"Killing remaining process {proc.pid}")
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        time.sleep(1)

    def _stop_via_pid(self):
        """Fallback method to stop via PID."""
        import subprocess
        import time

        pid = self.launch_json["data"]["pid"]
        try:
            port = self.get_http_port()
            subprocess.run(["pkill", "-f", f"agent-server.*--port.*{port}"], check=False)
            time.sleep(1)

            subprocess.run(["kill", str(pid)], check=False)
            time.sleep(1)
        except Exception as e:
            log.warning(f"Failed to stop agent server with PID {pid}: {e}")

    def stop(self):
        if hasattr(self, "_process"):
            try:
                all_processes = self._get_process_tree()
                self._terminate_process_gracefully()
                self._cleanup_child_processes(all_processes)

                # Wait for log capture threads to finish
                for thread in self._log_capture_threads:
                    thread.join(timeout=1)
            except Exception as e:
                log.warning(f"Error stopping agent server process: {e}")
        else:
            self._stop_via_pid()
