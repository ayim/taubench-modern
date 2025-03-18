import asyncio
import json
import random
import traceback
from pathlib import Path

import anywidget
import requests
import traitlets
import websockets
from websockets.exceptions import ConnectionClosed


from agent_server_types_v2.delta import combine_generic_deltas, GenericDelta


# In dev, point to your local dev server
ESM = "http://localhost:5173/src/index.tsx?anywidget"
CSS = ""


class AgentApiClient:
    """Basic client for your FastAPI server's threads endpoints."""

    def __init__(self, base_url="http://localhost:8000/api/v2"):
        self.base_url = base_url.rstrip("/")

    def list_threads(self, agent_id: str):
        url = f"{self.base_url}/threads?agent_id={agent_id}"
        resp = requests.get(url)
        resp.raise_for_status()
        return resp.json()  # list of {thread_id, name, messages, ...}

    def create_thread(self, agent_id: str, thread_name: str = "New Thread"):
        url = f"{self.base_url}/threads"
        payload = {"agent_id": agent_id, "name": thread_name, "messages": []}
        resp = requests.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()  # a single Thread object

    def get_thread(self, thread_id: str):
        url = f"{self.base_url}/threads/{thread_id}"
        resp = requests.get(url)
        resp.raise_for_status()
        return resp.json()  # a single Thread object

    def add_message_to_thread(self, thread_id: str, message: dict):
        url = f"{self.base_url}/threads/{thread_id}/messages"
        resp = requests.post(url, json=message)
        resp.raise_for_status()
        return resp.json()  # a single Thread object

    def delete_thread(self, thread_id: str):
        url = f"{self.base_url}/threads/{thread_id}"
        resp = requests.delete(url)
        resp.raise_for_status() # This should just return 204


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

    threads = traitlets.List(traitlets.Dict()).tag(sync=True)
    selected_thread_id = traitlets.Unicode(allow_none=True).tag(sync=True)
    selected_thread_name = traitlets.Unicode(allow_none=True).tag(sync=True)
    messages = traitlets.List(traitlets.Dict()).tag(sync=True)
    is_loading = traitlets.Bool(default_value=False).tag(sync=True)
    status_message = traitlets.Unicode(default_value="Ready").tag(sync=True)

    def __init__(self, agent_id, base_url="http://localhost:8000/api/v2", **kwargs):
        super().__init__(agent_id=agent_id, base_url=base_url, **kwargs)
        self.api = AgentApiClient(base_url)
        self._ws = None
        self._ws_task = None

        self.handle_custom_message()

        # Fetch threads
        self.refresh_threads()
        if self.threads:
            # Select the first thread by default
            self.selected_thread_id = self.threads[0]["thread_id"]
            self.selected_thread_name = self.threads[0].get("name", "")
            self.refresh_messages()

    def refresh_threads(self):
        try:
            data = self.api.list_threads(self.agent_id)
            self.threads = data
        except Exception as e:
            print("Error listing threads:", e)
            self.threads = []

    def refresh_messages(self):
        if not self.selected_thread_id:
            self.messages = []
            self.selected_thread_name = ""
            return
        try:
            thread_data = self.api.get_thread(self.selected_thread_id)
            self.selected_thread_name = thread_data.get("name", "")
            self.messages = thread_data.get("messages", [])
        except Exception as e:
            print(f"Error fetching thread={self.selected_thread_id}: {e}")

    @traitlets.observe("selected_thread_id")
    def _on_thread_change(self, change):
        if change["new"]:
            self.refresh_messages()
            self._ws_connect_task = asyncio.ensure_future(
                self._start_websocket(change["new"]),
            )

    # ~~~~~ WebSocket logic ~~~~~
    async def _start_websocket(self, thread_id: str):
        """Close existing ws, open a new one for the chosen thread."""
        await self._close_websocket()

        ws_url = f"ws://localhost:8000/api/v2/runs/{self.agent_id}/stream"
        try:
            self._ws = await websockets.connect(ws_url)
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

    async def _ws_receive_loop(self):  # noqa: C901
        try:
            while True:
                msg = await self._ws.recv()
                message_dict = json.loads(msg)

                # print(f"Received message: {message_dict}")

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
                        self.messages = [*self.messages.copy(), {
                            "role": "agent",
                            "content": [],
                        }]
                    elif event_type == "message_content":
                        delta = GenericDelta.model_validate(message_dict["delta"].get("delta", {}))
                        # Need to _assign_ to update in traitlets
                        self.messages = [*self.messages[:-1].copy(), combine_generic_deltas(
                            [delta], self.messages[-1],
                        )]
                elif msg_type == "error":
                    print("[WS Error]", message_dict.get("message"))
                    print(message_dict.get("stack_trace"))
                    self.is_loading = False
                    self.status_message = "Error: " + message_dict.get("message", "Unknown error")
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
            self.status_message = f"Error: {str(e)}"

    def _append_message(self, role: str, text: str):
        current = list(self.messages)
        current.append({"role": role, "content": [{"kind": "text", "text": text}]})
        self.messages = current

    def handle_custom_message(self):
        def _handle_msg(widget, content, buffers):
            print(f"Received message: {content}")
            msg_type = content.get("type")
            if msg_type == "select_thread":
                thread_id = content.get("thread_id")
                if thread_id:
                    widget.selected_thread_id = thread_id
            elif msg_type == "new_thread":
                widget.create_new_thread()
            elif msg_type == "user_input":
                user_text = content.get("text")
                if user_text and widget.selected_thread_id:
                    asyncio.create_task(widget._send_user_input_over_ws(user_text))
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
                # Update the thread with what the user typed
                self.api.add_message_to_thread(
                    self.selected_thread_id,
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": user_text,
                            },
                        ],
                    },
                )

                # Send initial handshake
                init_payload = {
                    "agent_id": self.agent_id,
                    "thread_id": self.selected_thread_id,
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
        try:
            print(f"Deleting thread={thread_id}, selected_thread_id={self.selected_thread_id}")
            # Close the WebSocket connection if we're deleting the currently selected thread
            if thread_id == self.selected_thread_id:
                asyncio.create_task(self._close_websocket())
                self.selected_thread_id = None
                self.selected_thread_name = None
                self.messages = []
            
            # Call the API to delete the thread
            self.api.delete_thread(thread_id)
            
            # Refresh the thread list
            self.refresh_threads()
            self.status_message = "Thread deleted successfully"
        except Exception as e:
            self.status_message = f"Error deleting thread: {str(e)}"
            print(f"Error deleting thread: {e}")

    def create_new_thread(self):
        try:
            # Generate a fun thread name
            thread_name = self._generate_fun_thread_name()
            new_thread = self.api.create_thread(self.agent_id, thread_name)
            self.refresh_threads()
            self.selected_thread_id = new_thread["thread_id"]
            self.selected_thread_name = new_thread["name"]
            self.refresh_messages()
            self._ws_connect_task = asyncio.ensure_future(
                self._start_websocket(new_thread["thread_id"]),
            )
        except Exception as e:
            print("Error creating thread:", e)
