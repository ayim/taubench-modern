import asyncio
import sys
from asyncio import CancelledError, create_task
from collections.abc import AsyncIterator
from dataclasses import asdict

from structlog import get_logger

from agent_platform.core.kernel import Kernel
from agent_platform.core.streaming.delta import StreamingDelta, StreamingDeltaAgentFinished
from agent_platform.core.streaming.incoming import IncomingDelta
from agent_platform.server.agent_architectures import BaseAgentRunner  # TODO move to core?

logger = get_logger(__name__)


class Session:
    """
    In-process session for an agent run.
    """

    def __init__(self, *, runner: BaseAgentRunner, kernel: Kernel):
        self.runner = runner
        self.kernel = kernel

        self._incoming_messages: asyncio.Queue[IncomingDelta] = asyncio.Queue()
        self._outgoing_messages: asyncio.Queue[StreamingDelta] = asyncio.Queue()
        self._tasks: set[asyncio.Task] = set()
        self._started = False
        self._stopping = asyncio.Event()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.stop()

    def __aiter__(self) -> AsyncIterator[StreamingDelta]:
        return self._iter_events()

    async def start(self):
        if self._started:
            return
        self._started = True
        self._stopping.clear()
        self._run_task = asyncio.create_task(self._run(), name="session-runner")
        logger.info("agent session started")

    async def stop(self):
        if not self._started:
            return
        self._stopping.set()
        await self._cancel_tasks()
        self._started = False
        logger.info("agent session closed")

    async def send(self, message: IncomingDelta) -> None:
        await self._incoming_messages.put(message)

    def events(self) -> AsyncIterator[StreamingDelta]:
        return self._iter_events()

    async def _run(self):
        try:
            # TODO when it is read should I send AgentReady event?
            await self.runner.start()

            invoke_task = create_task(self.runner.invoke(self.kernel))
            recv_task = asyncio.create_task(self._recv_loop(), name="recv-from-runner")
            send_task = asyncio.create_task(self._send_loop(), name="send-to-runner")

            self._tasks = {recv_task, send_task, invoke_task}

            done, pending = await asyncio.wait(self._tasks, return_when=asyncio.FIRST_COMPLETED)

            logger.info("terminating run")
            self._stopping.set()

            for t in pending:
                t.cancel()
            await asyncio.gather(*pending, return_exceptions=True)

        except Exception as e:
            print(f"[run] run error: {type(e).__name__}: {e}", file=sys.stderr)
        finally:
            self._tasks.clear()

    async def _recv_loop(self):
        try:
            async for event in self.runner.get_event_stream():
                await self._outgoing_messages.put(event)
                if isinstance(event, StreamingDeltaAgentFinished):
                    break
            logger.info("[recv] closing event stream")
        except CancelledError:
            logger.info("[recv] Receiving from task cancelled")
        except Exception as e:
            logger.info(f"[recv] error: {type(e).__name__}: {e}", file=sys.stderr)
        finally:
            # TODO I should signal to close the queue
            pass

    async def _send_loop(self):
        try:
            while not self._stopping.is_set():
                msg = await self._incoming_messages.get()
                try:
                    await self.runner.dispatch_event(asdict(msg))
                finally:
                    self._incoming_messages.task_done()
        except CancelledError:
            pass
        except Exception as e:
            logger.info(f"[send] error: {type(e).__name__}: {e}", file=sys.stderr)

    async def _cancel_tasks(self):
        if not self._tasks:
            return
        for t in list(self._tasks):
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def _iter_events(self) -> AsyncIterator[StreamingDelta]:
        try:
            while True:
                event = await self._outgoing_messages.get()
                try:
                    if isinstance(event, StreamingDeltaAgentFinished):
                        return
                    yield event
                finally:
                    self._outgoing_messages.task_done()
        finally:
            pass
