from asyncio import CancelledError
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import structlog

from agent_platform.core.agent_architectures.architecture_info import ArchitectureInfo
from agent_platform.core.kernel import Kernel
from agent_platform.core.streaming.delta import (
    StreamingDelta,
    StreamingDeltaAgentError,
    StreamingDeltaAgentFinished,
)
from agent_platform.core.streaming.incoming import IncomingDelta
from agent_platform.server.agent_architectures.base_runner import BaseAgentRunner

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class InProcessAgentRunner(BaseAgentRunner):
    """Runs the CA logic in the same Python process. For trusted CAs only."""

    def __init__(self, package_name: str, version: str, thread_id: str):
        self.package_name = package_name
        self.version = version
        self.thread_id = thread_id
        self.entry_func = None

        self._started = False
        self._kernel = None

    async def start(self) -> None:
        from importlib.metadata import entry_points

        # If the CA is already started, do nothing
        if self._started:
            return

        # Possibly load the CA entrypoint:
        self._started = True
        entry_points = entry_points(group="agent_platform.architectures")

        self.entry_func = None
        for ep in entry_points:
            if ep.name == self.package_name:
                self.entry_func = ep.load()
                break

        if not self.entry_func:
            raise RuntimeError(f"No entrypoint found for {self.package_name}")

        # You might also do some “init” if the CA has a stateful setUp
        # Or spawn a background task for reading events, etc. Up to you.

    async def invoke(self, kernel: Kernel) -> None:
        try:
            self._kernel = kernel
            if self.entry_func:
                await self.entry_func(kernel)
        except CancelledError:
            logger.info(
                "Agent architecture invocation cancelled, likely client disconnected",
            )
        except Exception as e:
            import traceback

            await kernel.outgoing_events.dispatch(
                StreamingDeltaAgentError(
                    error_message=str(e),
                    error_stack_trace=traceback.format_exc(),
                    run_id=kernel.run.run_id,
                    thread_id=kernel.run.thread_id,
                    agent_id=kernel.run.agent_id,
                    timestamp=datetime.now(UTC),
                ),
            )
        finally:
            await kernel.outgoing_events.dispatch(
                StreamingDeltaAgentFinished(
                    run_id=kernel.run.run_id,
                    thread_id=kernel.run.thread_id,
                    agent_id=kernel.run.agent_id,
                    timestamp=datetime.now(UTC),
                ),
            )

    def get_event_stream(self) -> AsyncIterator[StreamingDelta]:
        if not self._kernel:
            raise RuntimeError("Kernel not attached")
        return self._kernel.outgoing_events.stream()

    async def dispatch_event(self, event: IncomingDelta) -> None:
        if not self._kernel:
            raise RuntimeError("Kernel not attached")
        await self._kernel.incoming_events.dispatch(event)

    async def stop(self) -> None:
        pass

    @staticmethod
    def get_architectures() -> list[ArchitectureInfo]:
        from importlib.metadata import entry_points, version
        from inspect import getmodule
        from logging import getLogger

        logger = getLogger(__name__)

        # Load from the agent_platform.architectures entrypoint
        eps = entry_points(group="agent_platform.architectures")
        architectures = []

        for ep in eps:
            # Default built-in for in-process architectures
            arch_info = {"name": ep.name, "built_in": True}

            try:
                # Get version information
                arch_info["version"] = version(
                    ep.dist.name if ep.dist else ep.name,
                )
            except Exception:
                arch_info["version"] = "0.0.1"

            try:
                # Load the entry point function
                entry_func = ep.load()
                # Get the module of the entry point function
                module = getmodule(entry_func)
                # Get module docstring
                if module.__doc__:
                    arch_info["description"] = module.__doc__.strip()
                else:
                    arch_info["description"] = "No description available."

                # Extract other metadata from module if available
                other_metadata_fields = (
                    ArchitectureInfo.PACKAGE_ATTRIBUTES_TO_ARCHITECTURE_INFO.keys()
                )
                for meta_attr in other_metadata_fields:
                    if hasattr(module, meta_attr):
                        # Convert attribute name from "__attr__" to "attr"
                        key = meta_attr.strip("_")
                        arch_info[key] = getattr(module, meta_attr)
            except Exception as e:
                # If we can't extract metadata, still include what we have
                logger.debug(f"Error extracting metadata for {ep.name}: {e}")
                pass

            architectures.append(arch_info)

        return [ArchitectureInfo.model_validate(arch) for arch in architectures]
