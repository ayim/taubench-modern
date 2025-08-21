import asyncio
import json
import sys
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
import websockets
from websockets import ConnectionClosed, WebSocketClientProtocol

OnMessage = Callable[[dict[str, Any]], Awaitable[None]]

logger = structlog.get_logger(__name__)


class WebSocketClient:
    def __init__(
        self,
        url: str,
        on_message: OnMessage,
        backoff: float = 1.0,
        max_backoff: float = 30.0,
    ):
        self.url = url
        self.backoff_initial = max(0.1, backoff)
        self.max_backoff = max(self.backoff_initial, max_backoff)
        self.on_message: OnMessage = on_message

        self._ws: WebSocketClientProtocol | None = None
        self._outgoing: asyncio.Queue[str] = asyncio.Queue()
        self._tasks: set[asyncio.Task] = set()
        self._started = False
        self._stopping = asyncio.Event()
        self._connected = asyncio.Event()

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.stop()

    async def start(self):
        if self._started:
            return
        self._started = True
        self._stopping.clear()
        self._run_task = asyncio.create_task(self._run(), name="ws-runner")

    async def stop(self):
        if not self._started:
            return
        self._stopping.set()
        await self._cancel_tasks()
        await self._cleanup_connection()
        self._started = False
        self._connected.clear()

    async def send_json(self, obj: dict[str, Any]) -> None:
        await self._outgoing.put(json.dumps(obj))

    async def _run(self):
        backoff = self.backoff_initial
        while not self._stopping.is_set():
            try:
                self._ws = await websockets.connect(self.url)
                self._connected.set()
                recv_task = asyncio.create_task(self._recv_loop(), name="ws-recv")
                send_task = asyncio.create_task(self._send_loop(), name="ws-send")
                self._tasks = {recv_task, send_task}

                done, pending = await asyncio.wait(self._tasks, return_when=asyncio.FIRST_COMPLETED)
                logger.info(f"websocket task {done.pop().get_name()} completed")

                # if one loop exits, signal stop to the other
                self._stopping.set()

                for t in pending:
                    t.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                logger.info("Websocket tasks terminated")

            except Exception as e:
                print(f"[run] connect/run error: {type(e).__name__}: {e}", file=sys.stderr)
            finally:
                await self._cleanup_connection()
                self._tasks.clear()
                self._connected.clear()

            if self._stopping.is_set():
                break

            # Reconnect with exponential backoff
            print(f"[run] reconnecting in {backoff:.1f}s...")
            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=backoff)
                break  # stopped during backoff
            except TimeoutError:
                pass
            backoff = min(self.max_backoff, backoff * 2)

    async def _recv_loop(self):
        assert self._ws is not None
        try:
            async for msg in self._ws:
                try:
                    event = json.loads(msg)
                except Exception as e:
                    print(f"[recv][parse] {type(e).__name__}: {e}", file=sys.stderr)
                await self.on_message(event)
            logger.info(
                f"[recv] closing handshake code={self._ws.close_code} "
                f"reason={self._ws.close_reason}"
            )
        except ConnectionClosed as e:
            logger.info(f"[recv] connection closed: code={e.code} reason={e.reason}")
        except Exception as e:
            logger.info(f"[recv] error: {type(e).__name__}: {e}", file=sys.stderr)

    async def _send_loop(self):
        assert self._ws is not None
        try:
            while not self._stopping.is_set():
                msg = await self._outgoing.get()
                await self._ws.send(msg)
        except ConnectionClosed as e:
            logger.info(f"[send] connection closed: code={e.code} reason={e.reason}")
        except Exception as e:
            logger.info(f"[send] error: {type(e).__name__}: {e}", file=sys.stderr)

    async def _cancel_tasks(self):
        if not self._tasks:
            return
        for t in list(self._tasks):
            t.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def _cleanup_connection(self):
        ws, self._ws = self._ws, None
        if ws and not ws.closed:
            try:
                await ws.close(code=1000, reason="client stop")
            except Exception:
                pass
