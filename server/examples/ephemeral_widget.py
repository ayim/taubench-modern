import asyncio
import json
from uuid import uuid4

import anywidget
import requests
import traitlets
import websockets
from websockets.exceptions import ConnectionClosed

from agent_platform.core.delta import GenericDelta, combine_generic_deltas
from agent_platform.core.payloads.upsert_agent import UpsertAgentPayload
from agent_platform.core.thread import (
    Thread,
    ThreadAgentMessage,
    ThreadMessage,
    ThreadTextContent,
    ThreadUserMessage,
)
from agent_platform.core.tools.tool_definition import ToolDefinition


def is_url_accessible(url: str) -> bool:
    try:
        from requests.status_codes import codes

        response = requests.get(url, timeout=1.5)
        print(f"GET request to {url} returned status code {response.status_code}")
        return response.status_code < codes.BAD_REQUEST
    except requests.RequestException as ex:  # pragma: no cover - best effort
        print(f"Error checking if {url} is accessible: {ex}")
        return False


DEV_ESM = "http://localhost:5173/src/index.tsx?anywidget"
if is_url_accessible(DEV_ESM):
    print("Using widget in dev mode (hot-reloading)")
    ESM = DEV_ESM
else:
    print("Using static widget")
    ESM = "./debug_widget/static/index.js"

DEV_CSS = ""
CSS = (
    DEV_CSS if DEV_CSS and is_url_accessible(DEV_CSS) else "./debug_widget/static/debug-widget.css"
)


class EphemeralChatWidget(anywidget.AnyWidget):
    """Debug chat widget for ephemeral agents."""

    _esm = ESM
    _css = CSS

    agent_id = traitlets.Unicode().tag(sync=True)
    base_url = traitlets.Unicode().tag(sync=True)

    threads: list[Thread]
    threads_out = traitlets.List(traitlets.Dict()).tag(sync=True)

    selected_thread_id: str | None
    selected_thread_id_out = traitlets.Unicode(allow_none=True).tag(sync=True)

    selected_thread_name: str | None
    selected_thread_name_out = traitlets.Unicode(allow_none=True).tag(sync=True)

    messages: list[ThreadMessage]
    messages_out = traitlets.List(traitlets.Dict()).tag(sync=True)

    is_loading = traitlets.Bool(default_value=False).tag(sync=True)
    status_message = traitlets.Unicode(default_value="Ready").tag(sync=True)
    active_thread_artifacts = traitlets.List(traitlets.Dict()).tag(sync=True)

    def __init__(
        self,
        ephemeral_agent: UpsertAgentPayload,
        *,
        base_url: str = "http://localhost:8000/api/v2",
        client_tools: list[ToolDefinition] | None = None,
        **kwargs,
    ):
        resolved_id = ephemeral_agent.agent_id or "ephemeral"
        super().__init__(agent_id=resolved_id, base_url=base_url, **kwargs)
        self.ephemeral_agent = ephemeral_agent
        self.client_tools = client_tools or []
        self._ws = None
        self._ws_task = None
        self.active_run_id = None
        self.active_thread_id = None

        thread = Thread(
            user_id=ephemeral_agent.user_id or "debug-user",
            agent_id=resolved_id,
            name="Ephemeral Thread",
            thread_id=str(uuid4()),
            messages=[],
        )
        self.messages = []
        self.messages_out = []
        self.active_thread_artifacts = []
        self.selected_thread_name = thread.name
        self.threads = [thread]
        self.threads_out = [thread.model_dump()]
        self.selected_thread_id = thread.thread_id
        self.selected_thread_id_out = thread.thread_id
        self.selected_thread_name_out = thread.name

        self.handle_custom_message()

    # ------------------------------------------------------------------
    # Thread / message helpers
    # ------------------------------------------------------------------
    def refresh_messages(self) -> None:
        self.messages_out = [m.model_dump() for m in self.messages]
        self.selected_thread_name_out = self.selected_thread_name

    @traitlets.observe("selected_thread_id_out")
    def _on_thread_change(self, change):
        if change["new"]:
            self.refresh_messages()

    def _append_message(self, role: str, text: str) -> None:
        current = list(self.messages)
        if role == "user":
            current.append(ThreadUserMessage(content=[ThreadTextContent(text=text)]))
        else:
            current.append(ThreadAgentMessage(content=[ThreadTextContent(text=text)]))
        self.messages = current
        self.messages_out = [m.model_dump() for m in current]

    # ------------------------------------------------------------------
    # Websocket logic
    # ------------------------------------------------------------------
    async def _start_websocket(self) -> None:
        await self._close_websocket()
        ws_base = self.base_url.replace("https://", "wss://").replace("http://", "ws://")
        ws_url = f"{ws_base}/runs/ephemeral/stream"
        try:
            self._ws = await websockets.connect(ws_url)  # type: ignore
        except Exception as e:  # pragma: no cover - network
            print("WebSocket connection failed:", e)
            return
        self._ws_task = asyncio.create_task(self._ws_receive_loop())

    async def _close_websocket(self) -> None:
        if self._ws_task:
            self._ws_task.cancel()
            self._ws_task = None
        if self._ws:
            try:
                await self._ws.close()
            except Exception:  # pragma: no cover - best effort
                pass
        self._ws = None

    async def _ws_receive_loop(self) -> None:  # noqa: C901, PLR0912
        try:
            while True and self._ws:
                msg = await self._ws.recv()
                message_dict = json.loads(msg)

                if "event_type" in message_dict and message_dict["event_type"] == "agent_ready":
                    self.active_thread_id = message_dict["thread_id"]
                    self.active_run_id = message_dict["run_id"]
                    continue

                if "event_type" not in message_dict:
                    print("Unknown WS message:", msg)
                    continue

                msg_type = message_dict["event_type"]
                if msg_type == "request_user_input":
                    print(
                        "[WS] The agent wants user input. We'll wait "
                        "for a 'user_input' from the widget."
                    )
                    self.status_message = "Waiting for your input..."
                    self.is_loading = False
                elif msg_type == "message_begin":
                    self.is_loading = True
                    self.status_message = "Message streaming..."
                    self.messages = [*self.messages.copy(), ThreadAgentMessage(content=[])]
                elif msg_type == "message_content":
                    delta = GenericDelta.model_validate(message_dict["delta"])
                    self.messages = [
                        *self.messages[:-1].copy(),
                        ThreadAgentMessage.model_validate(
                            combine_generic_deltas([delta], self.messages[-1].model_dump())
                        ),
                    ]
                    self.messages_out = [m.model_dump() for m in self.messages]
                elif msg_type == "agent_error":
                    print("[WS Error]", message_dict.get("message"))
                    print(message_dict.get("stack_trace"))
                    self.is_loading = False
                    self.status_message = "Error: " + message_dict.get("message", "Unknown error")
                elif msg_type == "agent_finished":
                    self.is_loading = False
                    self.status_message = "Agent done"
                    try:
                        await self._ws.close()
                    except Exception:  # pragma: no cover - best effort
                        pass
                else:
                    pass
        except ConnectionClosed:
            print("[WS] Connection closed")
            self.is_loading = False
            self.status_message = "Ready"
            self._ws = None
        except asyncio.CancelledError:  # pragma: no cover - cancellation
            pass
        except Exception as e:  # pragma: no cover - unexpected errors
            print("[WS] Unexpected error:", e)
            self.is_loading = False
            self.status_message = f"Error: {e!s}"

    async def _send_user_input_over_ws(self, user_text: str) -> None:
        self._append_message(role="user", text=user_text)
        self.is_loading = True
        self.status_message = "Waiting for agent response..."
        try:
            await self._start_websocket()
        except Exception as e:  # pragma: no cover - network
            print("[WS] Error connecting:", e)
            self.is_loading = False
            self.status_message = "Error: Failed to connect to agent"
            return

        if self._ws:
            try:
                payload = {
                    "agent": self.ephemeral_agent.model_dump(),
                    "thread_id": self.selected_thread_id,
                    "name": self.selected_thread_name,
                    "messages": [m.model_dump() for m in self.messages],
                    "metadata": {},
                    "client_tools": [t.model_dump() for t in self.client_tools],
                }
                await self._ws.send(json.dumps(payload))
            except ConnectionClosed:
                print("[WS] Can't send user message, connection closed.")
                self.is_loading = False
                self.status_message = "Error: Connection closed"
            except Exception as e:  # pragma: no cover - network
                print("[WS] Error sending user message:", e)
                self.is_loading = False
                self.status_message = "Error: Failed to send message"
        else:
            print("[WS] Not connected --- cannot send user message.")
            self.is_loading = False
            self.status_message = "Error: Not connected to agent"

    # ------------------------------------------------------------------
    # Frontend message handling
    # ------------------------------------------------------------------
    def handle_custom_message(self) -> None:
        def _handle_msg(widget, content, buffers):
            background_tasks = set()
            msg_type = content.get("type")
            if msg_type == "user_input":
                user_text = content.get("text")
                if user_text and widget.selected_thread_id:
                    send_task = asyncio.create_task(widget._send_user_input_over_ws(user_text))
                    background_tasks.add(send_task)
                    send_task.add_done_callback(background_tasks.discard)
            elif msg_type == "delete_thread":
                widget.status_message = "Delete not supported in ephemeral mode"
            elif msg_type == "new_thread":
                widget.status_message = "New thread not supported in ephemeral mode"
            else:
                print(f"Unknown message type: {msg_type}")

        self.on_msg(_handle_msg)

    def close(self) -> None:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            self._close_ws_task = loop.create_task(self._close_websocket())
        else:
            self._close_ws_task = loop.run_until_complete(self._close_websocket())
        super().close()
