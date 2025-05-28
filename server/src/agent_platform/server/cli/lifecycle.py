"""Handle the lifecycle of the server."""

import json
import os
import signal
import socket

import structlog
import uvicorn

from agent_platform.server.cli.args import ServerArgs
from agent_platform.server.cli.configurations import load_full_config
from agent_platform.server.constants import SystemConfig, SystemPaths, _hyphenated_name

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class ServerLifecycleManager:
    """Manages the lifecycle of the agent server including startup,
    locking, and shutdown."""

    def __init__(self, args: ServerArgs, name: str = SystemConfig.name):
        self.args = args
        self.name = name
        self.hyphenated_name = _hyphenated_name(self.name)
        self.host: str = args.host if args.host is not None else SystemConfig.host
        self.port: int = args.port if args.port is not None else SystemConfig.port
        self.mutex = None
        self.socket = None
        self.server = None
        self.bound_host: str = self.host
        self.actual_port: int = self.port
        self.pid_file = SystemPaths.data_dir / f"{self.hyphenated_name}.pid"

    def setup_directories(self) -> None:
        """Create and validate data and log directories."""
        try:
            logger.debug(f"Creating data directory at {SystemPaths.data_dir}")
            SystemPaths.data_dir.mkdir(parents=True, exist_ok=True)
            pretty_permissions = oct(SystemPaths.data_dir.stat().st_mode)
            logger.info(
                f"Data directory available at: {SystemPaths.data_dir} "
                f"(permissions: {pretty_permissions})",
            )
        except Exception as e:
            logger.exception(f"Failed to create data directory: {SystemPaths.data_dir}")
            raise RuntimeError(
                f"Failed to create data directory: {SystemPaths.data_dir}",
            ) from e

        try:
            logger.debug(f"Creating log directory at {SystemPaths.log_dir}")
            SystemPaths.log_dir.mkdir(parents=True, exist_ok=True)
            pretty_permissions = oct(SystemPaths.log_dir.stat().st_mode)
            logger.info(
                f"Log directory available at: {SystemPaths.log_dir} "
                f"(permissions: {pretty_permissions})",
            )
        except Exception as e:
            logger.exception(f"Failed to create log directory: {SystemPaths.log_dir}")
            raise RuntimeError(
                f"Failed to create log directory: {SystemPaths.log_dir}",
            ) from e

    def setup_parent_pid_monitor(self) -> None:
        """Set up parent PID monitoring if enabled."""
        if self.args.parent_pid:
            from sema4ai.common.autoexit import exit_when_pid_exits

            logger.info(
                f"Marking to exit when parent PID {self.args.parent_pid} exits.",
            )
            exit_when_pid_exits(self.args.parent_pid, soft_kill_timeout=5)

    def obtain_lock(self, timeout: int = 5) -> bool:
        """Obtain a mutex lock if requested.

        Args:
            timeout: The timeout for the lock.

        Returns:
            bool: True if lock was obtained or not required, False if lock failed
        """
        if not self.args.use_data_dir_lock:
            return True

        from sema4ai.common.app_mutex import obtain_app_mutex

        logger.debug("Attempting to obtain app mutex lock")
        self.mutex = obtain_app_mutex(
            kill_lock_holder=self.args.kill_lock_holder,
            data_dir=SystemPaths.data_dir,
            lock_basename=f"{self.hyphenated_name}.lock",
            app_name=self.name,
            timeout=timeout,
        )
        if self.mutex is None:
            logger.error("Failed to obtain app mutex lock. Exiting.")
            return False
        logger.debug("Successfully obtained app mutex lock")
        return True

    def bind_socket(self) -> bool:
        """Bind to socket and handle port conflicts.

        Returns:
            bool: True if socket binding was successful, False otherwise
        """
        # Create Uvicorn config and bind socket
        try:
            from agent_platform.server.app import create_app

            logger.debug("Creating Uvicorn config")
            config_kwargs = {
                "app": create_app(),
                "host": self.host,
                "port": self.port,
                "log_config": None,
            }

            config = uvicorn.Config(**config_kwargs)
            logger.debug(f"Uvicorn config created: {config_kwargs}")

            logger.debug(f"Attempting to bind to {self.host}:{self.port}")
            self.socket = _custom_bind_socket(config)

            # Get the actual port and host from the socket
            actual_socket_info = self.socket.getsockname()
            actual_host, self.actual_port = actual_socket_info[:2]
            logger.debug(
                f"Successfully bound socket to {actual_host}:{self.actual_port}",
            )

            # Handle special cases for host binding
            self._handle_host_binding(actual_host)

            # Create server instance
            self.server = uvicorn.Server(config)
            logger.info(
                f"{self.name.title()} will listen on {self.bound_host}:{self.actual_port}",
            )
            return True

        except (OSError, SystemExit) as e:
            e_msg = str(e) if isinstance(e, OSError) else f"Uvicorn exit code: {e}"
            if isinstance(e, OSError) and "Address already in use" in str(e):
                logger.error(
                    f"Port {self.port} is already in use. Address already in use.",
                )
            else:
                logger.error(f"Failed to bind socket: {e_msg}")

            logger.error("Cannot continue without binding to a socket. Exiting.")
            return False

    def _handle_host_binding(self, actual_host: str) -> None:
        """Handle the differences between requested and actual bound hosts."""
        if self.host == "0.0.0.0" and actual_host != self.host:
            logger.info(
                "Socket bound to all interfaces (0.0.0.0) but "
                f"actual socket reports: {actual_host}",
            )
            self.bound_host = self.host
        elif self.host == "::" and actual_host != self.host:
            logger.info(
                "Socket bound to all IPv6 interfaces (::) but "
                f"actual socket reports: {actual_host}",
            )
            self.bound_host = self.host
        elif actual_host != self.host and self.host not in ["localhost", "127.0.0.1"]:
            logger.warning(
                f"Requested host {self.host} differs from actual bound host {actual_host}",
            )
            self.bound_host = actual_host
        else:
            self.bound_host = self.host

    def write_pid_file(self) -> None:
        """Write PID file with server information."""
        host = self.bound_host
        addr_format = "%s://%s:%d"
        if ":" in host:
            # It's an IPv6 address
            addr_format = "%s://[%s]:%d"

        protocol_name = "http"  # TODO: Make this configurable
        base_url = addr_format % (protocol_name, host, self.actual_port)

        data = {
            "port": self.actual_port,
            "pid": os.getpid(),
            "base_url": base_url,
            "host": host,
        }

        if self.args.use_data_dir_lock:
            data["lock_file"] = (SystemPaths.data_dir / self.hyphenated_name).as_posix()
        else:
            data["lock_file"] = "<not used>"

        self.pid_file.write_text(json.dumps(data))
        logger.info(f"pid file: {self.pid_file}")

    def setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""

        def signal_handler(sig, frame):
            logger.info(f"Received signal {sig}, shutting down...")
            if self.server:
                self.server.should_exit = True

        # Register signal handlers for common termination signals
        for sig in [signal.SIGINT, signal.SIGTERM]:
            signal.signal(sig, signal_handler)

    def start(self) -> int:
        """Start the server and run it.

        Returns:
            int: Exit code (0 for success, 1 for failure)
        """
        if not self.socket or not self.server:
            logger.error("Cannot start server - socket or server not initialized")
            return 1

        try:
            logger.debug("Starting Uvicorn server with pre-bound socket")
            self.server.run(sockets=[self.socket])
            logger.debug("Uvicorn server completed normally")
            return 0
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received, shutting down...")
            return 0
        except Exception as e:
            logger.exception(f"Unexpected error running server: {e}")
            return 1

    def cleanup(self) -> None:
        """Perform cleanup on shutdown."""
        logger.info("Performing server cleanup...")
        if self.pid_file.exists():
            try:
                self.pid_file.unlink()
                logger.debug(f"Removed PID file: {self.pid_file}")
            except Exception as e:
                logger.warning(f"Failed to remove PID file: {e}")

        # Mutex will be automatically released when the object is destroyed
        self.mutex = None

    def run(self) -> int:
        """Run the complete server lifecycle.

        Returns:
            int: Exit code (0 for success, non-zero for failure)
        """
        try:
            self.setup_directories()
            self.setup_parent_pid_monitor()

            if not self.obtain_lock():
                return 1

            if not self.bind_socket():
                return 1

            self.write_pid_file()
            self.setup_signal_handlers()

            load_full_config()

            return self.start()
        except Exception as e:
            logger.exception(f"Error during server lifecycle: {e}")
            return 1
        finally:
            self.cleanup()


def _custom_bind_socket(config: uvicorn.Config) -> socket.socket:
    """
    This is a copy of config.bind_socket() with the sole intent of
    allowing us to set the socket options to SO_REUSEADDR or SOCK_STREAM
    depending on the platform (on windows SO_REUSEADDR would allow one
    process to bind to a port used by another process if SO_REUSEADDR is set).
    """
    import sys

    import click

    logger_args: list[str | int]
    if config.uds:  # pragma: py-win32
        path = config.uds
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.bind(path)
            uds_perms = 0o666
            os.chmod(config.uds, uds_perms)
        except OSError as exc:  # pragma: full coverage
            logger.error(str(exc))
            sys.exit(1)

        message = "Uvicorn running on unix socket %s (Press CTRL+C to quit)"
        sock_name_format = "%s"
        color_message = (
            "Uvicorn running on "
            + click.style(sock_name_format, bold=True)
            + " (Press CTRL+C to quit)"
        )
        logger_args = [config.uds]
    elif config.fd:  # pragma: py-win32
        sock = socket.fromfd(config.fd, socket.AF_UNIX, socket.SOCK_STREAM)
        message = "Uvicorn running on socket %s (Press CTRL+C to quit)"
        fd_name_format = "%s"
        color_message = (
            "Uvicorn running on "
            + click.style(fd_name_format, bold=True)
            + " (Press CTRL+C to quit)"
        )
        logger_args = [sock.getsockname()]
    else:
        family = socket.AF_INET
        addr_format = "%s://%s:%d"

        if config.host and ":" in config.host:  # pragma: full coverage
            # It's an IPv6 address.
            family = socket.AF_INET6
            addr_format = "%s://[%s]:%d"

        sock = socket.socket(family=family)
        if sys.platform == "win32":
            sock.setsockopt(socket.SOL_SOCKET, socket.SOCK_STREAM, 1)
        else:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((config.host, config.port))
        except OSError as exc:  # pragma: full coverage
            logger.error(str(exc))
            sys.exit(1)

        message = f"Uvicorn running on {addr_format} (Press CTRL+C to quit)"
        color_message = (
            "Uvicorn running on " + click.style(addr_format, bold=True) + " (Press CTRL+C to quit)"
        )
        protocol_name = "https" if config.is_ssl else "http"
        logger_args = [protocol_name, config.host, sock.getsockname()[1]]
    logger.info(message, *logger_args, extra={"color_message": color_message})
    sock.set_inheritable(True)
    return sock
