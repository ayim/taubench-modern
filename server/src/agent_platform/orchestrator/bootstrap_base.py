import logging
import re
import sys
import time
from concurrent.futures import Future
from contextlib import ExitStack
from enum import Flag, auto
from io import StringIO
from pathlib import Path
from typing import TYPE_CHECKING, Generic, TypeVar

if TYPE_CHECKING:
    from sema4ai.common.process import Process

logger = logging.getLogger(__name__)


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def is_debugger_active() -> bool:
    try:
        import pydevd  # type:ignore
    except ImportError:
        return False

    return bool(pydevd.get_global_debugger())


class ProcessExitedError(RuntimeError):
    pass


class Stream(Flag):
    """Enum representing the streams to monitor."""

    STDOUT = auto()
    STDERR = auto()
    BOTH = STDOUT | STDERR


# Type variable for the result of a precondition
T = TypeVar("T")


class BootstrapPrecondition(Generic[T]):
    """Base class for bootstrap preconditions.

    A precondition represents a condition that needs to be met during the bootstrap process,
    such as a port being available or an application starting.
    """

    def __init__(self, name: str, pattern: str, streams: Stream = Stream.BOTH) -> None:
        """Initialize the precondition.

        Args:
            name: A descriptive name for the precondition.
            pattern: The pattern to match to consider the precondition fulfilled.
            streams: The streams to monitor (default: both stdout and stderr).
        """
        self.name = name
        self.pattern = pattern
        self.streams = streams
        self.future: Future = Future()
        self._compiled_pattern = re.compile(pattern)

        logger.info(f"Registering precondition '{name}' with pattern: {pattern}")

    def __str__(self) -> str:
        return (
            f"class:{self.__class__.__name__}, name:{self.name}, pattern:{self.pattern}, "
            f"streams:{self.streams}"
        )

    def process_line(self, line: str) -> None:
        """Process a line from the output stream and check if it matches the pattern.

        Args:
            line: The line to process.
        """
        raise NotImplementedError("Subclasses must implement this method")

    def handle_result(self, result: T) -> None:
        """Handle the result when the precondition is met.

        Args:
            result: The result of the precondition.
        """
        logger.info(f"{self.name.capitalize()} detected")

    def register_with_process(self, process: "Process", stack: ExitStack) -> None:
        """Register the precondition with the process.

        Args:
            process: The process to register with.
            stack: The ExitStack to use for registering callbacks.
        """
        if Stream.STDOUT in self.streams:
            stack.enter_context(process.on_stdout.register(self.process_line))

        if Stream.STDERR in self.streams:
            stack.enter_context(process.on_stderr.register(self.process_line))


def remove_ansi_codes(line: str) -> str:
    """Remove ANSI codes from the line."""
    return re.sub(r"\x1b\[[0-9;]*m", "", line)


class PortPrecondition(BootstrapPrecondition[tuple[str, str]]):
    """A precondition that waits for a port to be available."""

    def __init__(self, pattern: str, streams: Stream = Stream.BOTH) -> None:
        """Initialize the port precondition.

        Args:
            pattern: The regexp to match the host and port.
            streams: The streams to monitor (default: both stdout and stderr).
        """
        super().__init__("port", pattern, streams)
        logger.info(f"Will match host/port with regexp: {pattern}")

    def process_line(self, line: str) -> None:
        """Process a line from the output stream and check if it contains host/port information.

        Args:
            line: The line to process.
        """
        if not self.future.done():
            line = remove_ansi_codes(line)
            matches = re.findall(self._compiled_pattern, line)

            if matches:
                host, port = matches[0]
                self.future.set_result((host, port))

    def handle_result(self, result: tuple[str, str]) -> None:
        """Handle the port detection result.

        Args:
            result: A tuple containing (host, port).
        """
        host, port = result
        assert host, "Host should not be empty"
        assert int(port) > 0, f"Expected port to be > 0. Found: {port}"
        logger.info(f"Port detected: {port}")


class ApplicationStartPrecondition(BootstrapPrecondition[bool]):
    """A precondition that waits for an application to start."""

    def __init__(self, pattern: str, streams: Stream = Stream.BOTH) -> None:
        """Initialize the application start precondition.

        Args:
            pattern: The regexp to match the application startup message.
            streams: The streams to monitor (default: both stdout and stderr).
        """
        super().__init__("app_start", pattern, streams)
        logger.info(f"Will match application start with regexp: {pattern}")

    def process_line(self, line: str) -> None:
        """Process a line from the output stream and check if it indicates application startup.

        Args:
            line: The line to process.
        """
        if not self.future.done():
            line = remove_ansi_codes(line)
            if re.search(self._compiled_pattern, line):
                self.future.set_result(True)

    def handle_result(self, result: bool) -> None:
        """Handle the application startup result.

        Args:
            result: True if the application has started.
        """
        logger.info("Application startup complete detected")


class BootstrapBase:
    # Default values
    _name: str = ""  # Must be set in the subclass
    _process: "Process | None" = None
    _host: str = ""
    _port: int = -1
    started: bool = False

    SHOW_OUTPUT = True

    def __init__(self, executable_path: Path | None = None) -> None:
        assert self._name, "Name must be set in the subclass"

        self._stdout = StringIO()
        self._stderr = StringIO()
        self._executable_path = str(executable_path.absolute()) if executable_path else None
        # For storing preconditions that need to be met during bootstrap
        self._bootstrap_preconditions: list[BootstrapPrecondition] = []

    @property
    def host(self) -> str:
        if not self.started:
            raise RuntimeError("The action server was not properly started (no host available)")

        assert self._host, "The action server was not properly started (no host available)"
        return self._host

    @property
    def port(self) -> int:
        if not self.started:
            raise RuntimeError("The action server was not properly started (no port available)")

        assert self._port > 0, "The action server was not properly started (no port available)"
        return self._port

    @property
    def process(self) -> "Process":
        assert self._process is not None, (
            "The action server was not properly started (process is None)."
        )
        return self._process

    def setup_output_files_and_wait_for_port(
        self,
        process: "Process",
        logs_dir: Path,
        match_host_port_regexp: str,
        timeout: int,
    ) -> None:
        """
        The idea is that the subclass will actually start the process and then
        it'll call this method to wait for the port to be printed by the process
        in the stdout.

        Args:
            process: The process to monitor.
            logs_dir: The directory to save the stdout/stderr.
            match_host_port_regexp: The regexp to match the host and port.
            timeout: The timeout to wait for the port to be available.
        """
        # Setup output files and then wait for the port
        self.setup_output_files(process, logs_dir)
        self.register_port_precondition(match_host_port_regexp)
        self.start_process_and_wait_for_preconditions(process, timeout)

    def setup_output_files(
        self,
        process: "Process",
        logs_dir: Path,
    ) -> None:
        """
        Sets up the output files for stdout and stderr of the process.

        Args:
            process: The process to monitor.
            logs_dir: The directory to save the stdout/stderr.
        """
        stdout_file = logs_dir / f"{self._name}-stdout.log"
        stderr_file = logs_dir / f"{self._name}-stderr.log"

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

    def register_port_precondition(
        self,
        match_host_port_regexp: str,
        streams: Stream = Stream.BOTH,
    ) -> None:
        """
        Registers a precondition to be notified when a port is available.

        Args:
            match_host_port_regexp: The regexp to match the host and port.
            streams: The streams to monitor (default: both stdout and stderr).
        """
        precondition = PortPrecondition(match_host_port_regexp, streams)
        self._bootstrap_preconditions.append(precondition)

    def register_application_start_precondition(
        self,
        match_application_start_regexp: str,
        streams: Stream = Stream.BOTH,
    ) -> None:
        """
        Registers a precondition to be notified when the application has started.

        Args:
            match_application_start_regexp: The regexp to match the application startup message.
            streams: The streams to monitor (default: both stdout and stderr).
        """
        precondition = ApplicationStartPrecondition(match_application_start_regexp, streams)
        self._bootstrap_preconditions.append(precondition)

    def start_process_and_wait_for_preconditions(
        self,
        process: "Process",
        timeout: int,
    ) -> None:
        """
        Starts the process and waits for all registered preconditions to be met.

        Args:
            process: The process to monitor.
            timeout: The timeout to wait for all preconditions to be met.
        """
        # Store the process reference
        self._process = process

        # Use context managers to handle precondition registration/unregistration
        with self._register_all_preconditions(process):
            # Start the process
            process.start()

            # Wait for all futures to complete
            for precondition in self._bootstrap_preconditions:
                logger.info(
                    f"Waiting for '{precondition.name}' precondition"
                    f" with pattern: {precondition.pattern}"
                )
                self._wait_for_precondition(process, precondition, timeout)

                # For port precondition, update the host and port
                if isinstance(precondition, PortPrecondition):
                    host, port = precondition.future.result()
                    self._host = host
                    self._port = int(port)

        # Clear registered preconditions after waiting is complete
        self._bootstrap_preconditions = []

        # Set started to true
        self.started = True

    def _register_all_preconditions(self, process: "Process"):
        """
        Register all preconditions with the process and return a context manager
        that will handle unregistering them when exited.

        Args:
            process: The process to register preconditions with.

        Returns:
            A context manager that will unregister all preconditions when exited.
        """
        # Use ExitStack to combine multiple context managers
        stack = ExitStack()

        for precondition in self._bootstrap_preconditions:
            precondition.register_with_process(process, stack)

        return stack

    def _wait_for_precondition(
        self,
        process: "Process",
        precondition: BootstrapPrecondition,
        timeout: int,
    ) -> None:
        """
        Waits for a precondition to be met.

        Args:
            process: The process to monitor.
            precondition: The precondition to wait for.
            timeout: The timeout to wait for the precondition to be met.
        """
        if timeout > 1:
            initial_time = time.monotonic()
            while True:
                try:
                    result = precondition.future.result(1)
                    break
                except TimeoutError as ex:
                    if is_debugger_active():
                        continue
                    if time.monotonic() - initial_time >= timeout:
                        raise TimeoutError(
                            f"Timeout waiting for {precondition.name} - {precondition}"
                        ) from ex
                    if not process.is_alive():
                        raise ProcessExitedError(
                            f"The process already exited with returncode: "
                            f"{process.returncode}\n"
                            f"{process}.\n"
                            f"Stdout: {self.get_stdout()}\n"
                            f"Stderr: {self.get_stderr()}\n"
                        ) from ex
        else:
            result = precondition.future.result(timeout)

        # Use the precondition's handle_result method to process the result
        precondition.handle_result(result)

    def stop(self) -> None:
        """
        Stops the process.
        """
        if self._process is not None:
            self._process.stop()
            self._process = None

    def get_stdout(self) -> str:
        return self._stdout.getvalue()

    def get_stderr(self) -> str:
        return self._stderr.getvalue()
