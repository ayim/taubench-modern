import asyncio
import atexit
import json
import os.path
import random
import traceback

import anywidget
import requests
import traitlets
import websockets
from websockets.exceptions import ConnectionClosed

from agent_platform.core.delta import GenericDelta, combine_generic_deltas
from agent_platform.core.kernel_interfaces.otel import OTelArtifact
from agent_platform.core.thread import (
    Thread,
    ThreadAgentMessage,
    ThreadMessage,
    ThreadTextContent,
    ThreadUserMessage,
)


# Check if dev server is available, otherwise use static files
def is_url_accessible(url):
    try:
        from requests.status_codes import codes

        response = requests.get(url, timeout=1.5)
        print(f"GET request to {url} returned status code {response.status_code}")
        return response.status_code < codes.BAD_REQUEST
    except requests.RequestException as ex:
        print(f"Error checking if {url} is accessible: {ex}")
        return False


# Development URL
DEV_ESM = "http://localhost:5173/src/index.tsx?anywidget"
# Use dev URL if accessible, otherwise fall back to static files
if is_url_accessible(DEV_ESM):
    print("Using widget in dev mode (hot-reloading)")
    ESM = DEV_ESM
else:
    print("Using static widget")
    ESM = "./debug_widget/static/index.js"

# Similarly for CSS
DEV_CSS = ""
CSS = (
    DEV_CSS
    if DEV_CSS and is_url_accessible(DEV_CSS)
    else "./debug_widget/static/style.css"
)


class AgentApiClient:
    """Basic client for your FastAPI server's threads endpoints."""

    def __init__(self, base_url="http://localhost:8000/api/v2"):
        self.base_url = base_url.rstrip("/")

    def list_threads(self, agent_id: str):
        url = f"{self.base_url}/threads?agent_id={agent_id}"
        resp = requests.get(url)
        resp.raise_for_status()
        return [Thread.model_validate(t) for t in resp.json()]

    def create_thread(self, agent_id: str, thread_name: str = "New Thread"):
        url = f"{self.base_url}/threads"
        payload = {"agent_id": agent_id, "name": thread_name, "messages": []}
        resp = requests.post(url, json=payload)
        resp.raise_for_status()
        return Thread.model_validate(resp.json())

    def get_thread(self, thread_id: str):
        url = f"{self.base_url}/threads/{thread_id}"
        resp = requests.get(url)
        resp.raise_for_status()
        return Thread.model_validate(resp.json())

    def get_thread_artifacts(self, thread_id: str):
        url = f"{self.base_url}/debug/artifacts/search?thread_id={thread_id}"
        resp = requests.get(url)
        resp.raise_for_status()
        return [OTelArtifact.model_validate(a) for a in resp.json()]

    def add_message_to_thread(self, thread_id: str, message: dict):
        url = f"{self.base_url}/threads/{thread_id}/messages"
        resp = requests.post(url, json=message)
        resp.raise_for_status()
        return Thread.model_validate(resp.json())

    def delete_thread(self, thread_id: str):
        url = f"{self.base_url}/threads/{thread_id}"
        resp = requests.delete(url)
        resp.raise_for_status()  # This should just return 204


class DebugChatWidget(anywidget.AnyWidget):
    """A two-panel chat widget that:
    - Lists threads (via REST) on the left
    - Shows messages on the right
    - Sends user messages to the agent via WebSocket
    - Receives agent messages in real time
    """

    # Reference your separate JS & CSS files
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

    def __init__(self, agent_id, base_url="http://localhost:8000/api/v2", **kwargs):
        super().__init__(agent_id=agent_id, base_url=base_url, **kwargs)
        self.api = AgentApiClient(base_url)
        self._ws = None
        self._ws_task = None
        self.active_run_id = None
        self.active_thread_id = None
        self.threads_to_runs = {}
        self.active_thread_artifacts = []
        self.selected_thread_id = None
        self.selected_thread_id_out = None
        self.selected_thread_name = None
        self.selected_thread_name_out = None
        self._temp_files = []  # Track all temp files for cleanup

        self.handle_custom_message()

        # Register cleanup on exit
        atexit.register(self._cleanup_temp_files)

        # Fetch threads
        self.refresh_threads()
        if self.threads:
            # Select the first thread by default
            self.selected_thread_id = self.threads[0].thread_id
            self.selected_thread_id_out = self.threads[0].thread_id
            self.selected_thread_name = self.threads[0].name
            self.selected_thread_name_out = self.threads[0].name
            self.refresh_messages()
            self.refresh_active_thread_artifacts()

    def refresh_threads(self):
        try:
            data = self.api.list_threads(self.agent_id)
            self.threads = data
            self.threads_out = [t.model_dump() for t in data]
        except Exception as e:
            print("Error listing threads:", e)
            self.threads = []
            self.threads_out = []

    def refresh_active_thread_artifacts(self):
        from tempfile import mkdtemp

        if not self.selected_thread_id:
            self._cleanup_temp_files()
            self.active_thread_artifacts = []
            return

        # Clean up previous temp files before creating new ones
        self._cleanup_temp_files()

        try:
            artifacts = self.api.get_thread_artifacts(self.selected_thread_id)
            new_thread_artifacts = []

            # Create a temp directory for this run's artifacts
            temp_dir = mkdtemp()
            self._temp_files.append(temp_dir)  # Track the directory for cleanup

            # Create files with artifact names in the temp directory
            for idx, artifact in enumerate(artifacts):
                try:
                    artifact_name = f"{idx:03d}-{artifact.name}"
                    # Sanitize filename to remove any invalid characters
                    safe_name = "".join(
                        c for c in artifact_name if c.isalnum() or c in "._- "
                    )

                    file_path = os.path.join(temp_dir, safe_name)
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(artifact.content.decode())

                    new_thread_artifacts.append(
                        {
                            "name": artifact_name,
                            "path": file_path,
                            "run_id": artifact.correlated_run_id,
                            "message_id": artifact.correlated_message_id,
                        },
                    )
                except Exception as e:
                    print(
                        f"Error creating file for artifact {artifact.name}: " f"{e}",
                    )

            self.active_thread_artifacts = new_thread_artifacts
        except Exception as e:
            print(
                "Error fetching thread artifacts "
                f"for thread_id={self.selected_thread_id}: {e}",
            )
            self.active_thread_artifacts = []

    def _cleanup_temp_files(self):
        """Clean up all tracked temporary files and directories."""
        import shutil

        paths_to_remove = self._temp_files.copy()
        self._temp_files = []

        for path in paths_to_remove:
            try:
                if os.path.isdir(path):
                    shutil.rmtree(path)
                elif os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                print(f"Error deleting temp path {path}: {e}")
                # Keep track of paths we failed to delete
                self._temp_files.append(path)

    def refresh_messages(self):
        if not self.selected_thread_id:
            self.messages = []
            self.selected_thread_name = ""
            self.selected_thread_name_out = ""
            self.messages_out = []
            return
        try:
            thread_data = self.api.get_thread(self.selected_thread_id)
            self.selected_thread_name = thread_data.name
            self.messages = thread_data.messages
            self.messages_out = [m.model_dump() for m in self.messages]
        except Exception as e:
            print(f"Error fetching thread={self.selected_thread_id}: {e}")

    @traitlets.observe("selected_thread_id_out")
    def _on_thread_change(self, change):
        if change["new"]:
            self.refresh_messages()
            self._ws_connect_task = asyncio.ensure_future(
                self._start_websocket(change["new"]),
            )

    # ~~~~~ WebSocket logic ~~~~~
    async def _start_websocket(self, thread_id: str | None):
        """Close existing ws, open a new one for the chosen thread."""
        if thread_id is None:
            print("No thread selected --- not connecting to WebSocket")
            return

        await self._close_websocket()

        ws_url = f"ws://localhost:8000/api/v2/runs/{self.agent_id}/stream"
        try:
            # No idea why types don't check for this... connect is definitely
            # defined in websockets/__init__.py (it does some lazy loading tho...)
            self._ws = await websockets.connect(ws_url)  # type: ignore
        except Exception as e:
            print("WebSocket connection failed:", e)
            return

        # Start background read loop
        self._ws_task = asyncio.create_task(self._ws_receive_loop())

    async def _close_websocket(self):
        if self._ws_task:
            self._ws_task.cancel()
            self._ws_task = None
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass
        self._ws = None

    async def _ws_receive_loop(self):  # noqa: C901, PLR0912, PLR0915
        try:
            while True and self._ws:
                msg = await self._ws.recv()
                message_dict = json.loads(msg)

                # print(f"Received message: {message_dict}")
                if "event" in message_dict and message_dict["event"] == "ready":
                    self.active_thread_id = message_dict["thread_id"]
                    self.active_run_id = message_dict["run_id"]
                    if self.active_thread_id not in self.threads_to_runs:
                        self.threads_to_runs[self.active_thread_id] = [
                            self.active_run_id,
                        ]
                    else:
                        self.threads_to_runs[self.active_thread_id].append(
                            self.active_run_id,
                        )
                    continue

                # If it has 'event' key, unwrap it
                if "event" in message_dict:
                    message_dict = message_dict["event"]

                if "type" not in message_dict:
                    print("Unknown WS message:", msg)
                    continue

                msg_type = message_dict["type"]
                if msg_type == "user_message_request":
                    # In a console example, we'd do input().
                    # Here, we rely on user input from the widget.
                    print(
                        "[WS] The agent wants user input. "
                        "We'll wait for a 'user_input' from the widget.",
                    )
                    self.status_message = "Waiting for your input..."
                    self.is_loading = False
                elif msg_type == "delta" and "delta" in message_dict:
                    event_type = message_dict["delta"].get("event_type")
                    if event_type == "message_begin":
                        self.is_loading = True
                        self.status_message = "Message streaming..."
                        self.messages = [
                            *self.messages.copy(),
                            ThreadAgentMessage(content=[]),
                        ]
                    elif event_type == "message_content":
                        delta = GenericDelta.model_validate(
                            message_dict["delta"].get("delta", {}),
                        )
                        # Need to _assign_ to update in traitlets
                        self.messages = [
                            *self.messages[:-1].copy(),
                            ThreadAgentMessage.model_validate(
                                combine_generic_deltas(
                                    [delta],
                                    self.messages[-1].model_dump(),
                                ),
                            ),
                        ]
                        self.messages_out = [m.model_dump() for m in self.messages]
                    elif event_type == "message_end":
                        # Refresh active thread artifacts
                        self.refresh_active_thread_artifacts()
                elif msg_type == "error":
                    print("[WS Error]", message_dict.get("message"))
                    print(message_dict.get("stack_trace"))
                    self.is_loading = False
                    self.status_message = "Error: " + message_dict.get(
                        "message",
                        "Unknown error",
                    )
                else:
                    # Possibly partial text or other event
                    pass

        except ConnectionClosed:
            print("[WS] Connection closed")
            self.is_loading = False
            self.status_message = "Ready"
            self._ws = None
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print("[WS] Unexpected error:", e)
            # traceback
            traceback.print_exc()
            self.is_loading = False
            self.status_message = f"Error: {e!s}"

    def _append_message(self, role: str, text: str):
        current = list(self.messages)
        if role == "user":
            current.append(
                ThreadUserMessage(
                    content=[ThreadTextContent(text=text)],
                ),
            )
        else:
            current.append(
                ThreadAgentMessage(
                    content=[ThreadTextContent(text=text)],
                ),
            )
        self.messages = current
        self.messages_out = [m.model_dump() for m in current]

    def handle_custom_message(self):
        def _handle_msg(widget, content, buffers):
            background_tasks = set()
            print(f"Received message: {content}")
            msg_type = content.get("type")
            if msg_type == "select_thread":
                thread_id = content.get("thread_id")
                if thread_id:
                    widget.selected_thread_id = thread_id
                    widget.selected_thread_id_out = thread_id
                    widget.refresh_active_thread_artifacts()
            elif msg_type == "new_thread":
                widget.create_new_thread()
            elif msg_type == "user_input":
                user_text = content.get("text")
                if user_text and widget.selected_thread_id:
                    send_task = asyncio.create_task(
                        widget._send_user_input_over_ws(user_text),
                    )
                    background_tasks.add(send_task)
                    send_task.add_done_callback(background_tasks.discard)
            elif msg_type == "delete_thread":
                thread_id = content.get("thread_id")
                if thread_id:
                    widget.delete_thread(thread_id)
            else:
                print(f"Unknown message type: {msg_type}")

        self.on_msg(_handle_msg)

    def _generate_fun_thread_name(self):
        """Generate a fun thread name."""
        adjectives = [
            "Curious",
            "Brilliant",
            "Friendly",
            "Clever",
            "Helpful",
            "Witty",
            "Thoughtful",
            "Creative",
            "Innovative",
            "Insightful",
            "Adventurous",
            "Energetic",
            "Cheerful",
            "Optimistic",
            "Peaceful",
            "Cosmic",
            "Magical",
            "Whimsical",
            "Dazzling",
            "Intriguing",
        ]
        nouns = [
            "Conversation",
            "Discussion",
            "Dialogue",
            "Chat",
            "Exploration",
            "Journey",
            "Discovery",
            "Adventure",
            "Quest",
            "Expedition",
            "Brainstorm",
            "Investigation",
            "Project",
            "Mission",
            "Venture",
            "Puzzle",
            "Challenge",
            "Endeavor",
            "Experiment",
            "Breakthrough",
        ]

        return f"{random.choice(adjectives)}-{random.choice(nouns)}"

    async def _send_user_input_over_ws(self, user_text: str):
        self._append_message(role="user", text=user_text)
        self.is_loading = True
        self.status_message = "Waiting for agent response..."

        # Always close existing connection and establish a new one
        # since the server closes the connection after each exchange
        try:
            await self._start_websocket(self.selected_thread_id)
        except Exception as e:
            print("[WS] Error connecting:", e)
            self.is_loading = False
            self.status_message = "Error: Failed to connect to agent"
            return

        if self._ws:
            try:
                if self.selected_thread_id is None:
                    print("No thread selected --- not sending user message")
                    return

                # Update the thread with what the user typed
                self.api.add_message_to_thread(
                    self.selected_thread_id,
                    ThreadUserMessage(
                        content=[ThreadTextContent(text=user_text)],
                    ).model_dump(),
                )

                # Send initial handshake
                init_payload = {
                    "agent_id": self.agent_id,
                    "thread_id": self.selected_thread_id,
                    "messages": [],
                }
                await self._ws.send(json.dumps(init_payload))
            except ConnectionClosed:
                print("[WS] Can't send user message, connection closed.")
                self.is_loading = False
                self.status_message = "Error: Connection closed"
            except Exception as e:
                print("[WS] Error sending user message:", e)
                self.is_loading = False
                self.status_message = "Error: Failed to send message"
        else:
            print("[WS] Not connected --- cannot send user message.")
            self.is_loading = False
            self.status_message = "Error: Not connected to agent"

    def close(self):
        """Override to ensure temp files are cleaned up when widget is closed."""
        # Clean up temp files
        self._cleanup_temp_files()

        # Close WebSocket
        loop = asyncio.get_event_loop()
        if loop.is_running():
            self._close_websocket_task = loop.create_task(
                self._close_websocket(),
            )
        else:
            self._close_websocket_task = loop.run_until_complete(
                self._close_websocket(),
            )
        super().close()

    def delete_thread(self, thread_id: str):
        """Delete a thread and refresh the thread list."""
        background_tasks = set()

        try:
            print(
                f"Deleting thread={thread_id}, "
                f"selected_thread_id={self.selected_thread_id}",
            )
            # Close the WebSocket connection if we're deleting the
            # currently selected thread
            if thread_id == self.selected_thread_id:
                close_task = asyncio.create_task(self._close_websocket())
                background_tasks.add(close_task)
                close_task.add_done_callback(background_tasks.discard)
                self.selected_thread_id = None
                self.selected_thread_name = None
                self.messages = []
                self.active_thread_artifacts = []
                self._cleanup_temp_files()

            # Call the API to delete the thread
            self.api.delete_thread(thread_id)

            # Refresh the thread list
            self.refresh_threads()
            self.status_message = "Thread deleted successfully"
        except Exception as e:
            self.status_message = f"Error deleting thread: {e!s}"
            print(f"Error deleting thread: {e}")

    def create_new_thread(self):
        try:
            # Generate a fun thread name
            thread_name = self._generate_fun_thread_name()
            new_thread = self.api.create_thread(self.agent_id, thread_name)
            self.refresh_threads()
            self.selected_thread_id = new_thread.thread_id
            self.selected_thread_id_out = new_thread.thread_id
            self.selected_thread_name = new_thread.name
            self.selected_thread_name_out = new_thread.name
            self.refresh_messages()
            self._ws_connect_task = asyncio.ensure_future(
                self._start_websocket(new_thread.thread_id),
            )
        except Exception as e:
            print("Error creating thread:", e)
