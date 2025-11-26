import json
import os
import threading
import time
from dataclasses import dataclass, field
from queue import Empty, Queue
from typing import Any
from urllib.parse import urlencode

import dotenv
import httpx
from jsonpatch import JsonPatch, JsonPatchException, JsonPointerException
from loguru import logger
from tau2.agent.base import (
    LocalAgent,
    ValidAgentInputMessage,
)
from tau2.agent.llm_agent import LLMAgent
from tau2.data_model.message import (
    AssistantMessage,
    Message,
    MultiToolMessage,
    ToolCall,
    ToolMessage,
    UserMessage,
)
from tau2.environment.tool import Tool
from tau2.registry import registry as tau_registry
from websocket import WebSocketApp

# --------------------------
# Configuration helpers
# --------------------------


def _find_nearest_env_file() -> str | None:
    current_file = os.path.abspath(__file__)
    while True:
        env_file = os.path.join(os.path.dirname(current_file), ".env")
        if os.path.exists(env_file):
            return env_file
        if current_file == os.path.dirname(current_file):
            return None
        current_file = os.path.dirname(current_file)


def _env_str(name: str, default: str = "") -> str:
    v = os.getenv(name)
    return v if v and v.strip() else default


def _env_first(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value and value.strip():
            return value
    return default


DEFAULT_WS_BASE = _env_str("SEMA4AI_BASE_URL", "ws://localhost:8000")
DEFAULT_ARCHITECTURE_NAME = "agent_platform.architectures.experimental_1"
DEFAULT_ARCHITECTURE_VERSION = "1.0.0"
HTTP_STATUS_OK = 200

ARCHITECTURE_ALIAS_MAP: dict[str, str] = {
    "default": "agent_platform.architectures.default",
    "experimental_1": "agent_platform.architectures.experimental_1",
    "experimental_2": "agent_platform.architectures.experimental_2",
    "experimental_3": "agent_platform.architectures.experimental_3",
}

ARCHITECTURE_VERSION_OVERRIDES: dict[str, str] = {
    "agent_platform.architectures.default": "1.0.0",
    "agent_platform.architectures.experimental_1": "2.0.0",
    "agent_platform.architectures.experimental_2": "2.0.0",
}


def _normalize_architecture_name(name: str | None) -> str:
    candidate = (
        name or os.getenv("TAU2_AGENT_ARCHITECTURE") or _env_str("SEMA4AI_TAU2_ARCHITECTURE")
    )
    candidate = candidate.strip() if candidate else ""
    key = candidate.lower().replace(" ", "_").replace("-", "_") if candidate else ""
    resolved = ARCHITECTURE_ALIAS_MAP.get(key)
    if resolved:
        return resolved
    if candidate:
        return candidate
    return DEFAULT_ARCHITECTURE_NAME


def _architecture_version(name: str) -> str:
    env_override = os.getenv("TAU2_AGENT_ARCHITECTURE_VERSION") or _env_str(
        "SEMA4AI_TAU2_ARCHITECTURE_VERSION"
    )
    if env_override:
        return env_override
    return ARCHITECTURE_VERSION_OVERRIDES.get(name, DEFAULT_ARCHITECTURE_VERSION)


# Standard runs stream path (non-ephemeral): /api/v2/runs/{agent_id}/stream

# How long we block on the event queue while waiting for the agent's "decision"
EVENT_POLL_TIMEOUT_SEC = float(os.getenv("SEMA4AI_EVENT_POLL_TIMEOUT_SEC", "60.0"))

# When building a simple text from streaming deltas, we append as chunks come in
MAX_ACCUM_SECONDS_FOR_PLAIN_ANSWER = float(os.getenv("SEMA4AI_MAX_ACCUM_SECONDS", "600.0"))

# --------------------------
# JSON shapes used by server
# --------------------------


def _ws_base_to_http_base(ws_base: str) -> str:
    # Convert ws:// -> http:// and wss:// -> https://
    if ws_base.startswith("ws://"):
        return "http://" + ws_base[len("ws://") :]
    if ws_base.startswith("wss://"):
        return "https://" + ws_base[len("wss://") :]
    # Assume already http(s)
    return ws_base


def _build_agent_payload_for_post(  # noqa: PLR0913
    runbook_text: str,
    agent_name: str,
    agent_description: str,
    *,
    platform: str | None = None,
    model: str | None = None,
    architecture: str | None = None,
) -> dict[str, Any]:
    # Try to dotenv load the nearest .env file to the current file
    nearest_env_file = _find_nearest_env_file()
    if nearest_env_file:
        dotenv.load_dotenv(nearest_env_file)

    selected_platform = (platform or _env_str("SEMA4AI_TAU2_PLATFORM", "openai")).strip()

    platform_configs = []
    if selected_platform == "openai":
        openai_api_key = _env_first("SEMA4AI_TAU2_OPENAI_API_KEY", "OPENAI_API_KEY")
        assert openai_api_key, "Set SEMA4AI_TAU2_OPENAI_API_KEY or OPENAI_API_KEY"
        platform_configs.append(
            {
                "kind": "openai",
                "openai_api_key": openai_api_key,
                "models": {
                    "openai": [
                        model or _env_first("SEMA4AI_TAU2_MODEL", "OPENAI_MODEL", default="gpt-5")
                    ],
                },
            }
        )
    elif selected_platform == "groq":
        groq_api_key = _env_first("SEMA4AI_TAU2_GROQ_API_KEY", "GROQ_API_KEY")
        assert groq_api_key, "Set SEMA4AI_TAU2_GROQ_API_KEY or GROQ_API_KEY"
        platform_configs.append(
            {
                "kind": "groq",
                "groq_api_key": groq_api_key,
                "models": {
                    "openai": [model or _env_str("SEMA4AI_TAU2_MODEL", "gpt-oss-20b")],
                },
            }
        )
    elif selected_platform == "bedrock":
        access_key = _env_first("SEMA4AI_TAU2_BEDROCK_ACCESS_KEY_ID", "AWS_ACCESS_KEY_ID")
        secret_key = _env_first("SEMA4AI_TAU2_BEDROCK_SECRET_ACCESS_KEY", "AWS_SECRET_ACCESS_KEY")
        assert access_key, "Set SEMA4AI_TAU2_BEDROCK_ACCESS_KEY_ID or AWS_ACCESS_KEY_ID"
        assert secret_key, "Set SEMA4AI_TAU2_BEDROCK_SECRET_ACCESS_KEY or AWS_SECRET_ACCESS_KEY"
        platform_configs.append(
            {
                "kind": "bedrock",
                "region_name": _env_first(
                    "SEMA4AI_TAU2_BEDROCK_REGION_NAME",
                    "AWS_REGION",
                    "AWS_DEFAULT_REGION",
                    default="us-east-1",
                ),
                "aws_access_key_id": access_key,
                "aws_secret_access_key": secret_key,
                "models": {
                    "anthropic": [model or _env_str("SEMA4AI_TAU2_MODEL", "claude-4-sonnet")],
                },
            }
        )
    else:
        raise ValueError(f"Unsupported platform: {selected_platform}")

    architecture_name = _normalize_architecture_name(architecture)
    return {
        "name": agent_name,
        "description": agent_description,
        "version": "1.0.0",
        "runbook": runbook_text,
        "platform_configs": platform_configs,
        "agent_architecture": {
            "name": architecture_name,
            "version": _architecture_version(architecture_name),
        },
        "action_packages": [],
        "mcp_servers": [],
        "question_groups": [],
        "observability_configs": [
            {
                "type": "langsmith",
                "api_url": "https://api.smith.langchain.com",
                "api_key": _env_str("LANGSMITH_API_KEY"),
                "settings": {
                    "project_name": "henkel-debug",
                },
            },
        ],
        "mode": "conversational",
        "extra": {},
        "advanced_config": {},
        "metadata": {"origin": "tau2"},
        "public": True,
    }


def _http_get_or_none(url: str, headers: dict[str, str] | None = None, timeout: float = 15.0):
    try:
        resp = httpx.get(url, headers=headers or {}, timeout=timeout)
        if resp.status_code == HTTP_STATUS_OK:
            return resp.json()
        return None
    except Exception as e:
        logger.debug(f"HTTP GET failed: {e}")
        return None


def _http_post_json(
    url: str, payload: dict[str, Any], headers: dict[str, str] | None = None, timeout: float = 15.0
) -> dict[str, Any]:
    resp = httpx.post(url, json=payload, headers=headers or {}, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _http_put_json(
    url: str, payload: dict[str, Any], headers: dict[str, str] | None = None, timeout: float = 15.0
) -> dict[str, Any]:
    resp = httpx.put(url, json=payload, headers=headers or {}, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _get_or_create_agent_id(  # noqa: PLR0913
    http_base: str,
    runbook_text: str,
    tools: list[dict[str, Any]],
    agent_name: str,
    agent_description: str,
    *,
    platform: str | None = None,
    model: str | None = None,
    architecture: str | None = None,
) -> str:
    agents_base = http_base.rstrip("/") + "/api/v2/agents"
    by_name_url = agents_base + "/by-name?" + urlencode({"name": agent_name})
    existing = _http_get_or_none(by_name_url)
    if existing and existing.get("agent_id"):
        agent_id = existing["agent_id"]
        try:
            # Ensure configuration is up to date (best-effort)
            payload = _build_agent_payload_for_post(
                runbook_text,
                agent_name,
                agent_description,
                platform=platform,
                model=model,
                architecture=architecture,
            )
            _http_put_json(f"{agents_base}/{agent_id}", payload)
        except Exception:
            pass
        return agent_id

    # Create if not found
    payload = _build_agent_payload_for_post(
        runbook_text,
        agent_name,
        agent_description,
        platform=platform,
        model=model,
        architecture=architecture,
    )
    created = _http_post_json(agents_base + "/", payload)
    if created.get("agent_id"):
        return created["agent_id"]

    # Fallback: try to fetch by name again (race condition handling)
    existing = _http_get_or_none(by_name_url)
    if existing and existing.get("agent_id"):
        return existing["agent_id"]

    raise RuntimeError("Failed to create or retrieve agent")


def _create_thread(
    http_base: str,
    agent_id: str,
    initial_messages: list[dict[str, Any]] | None = None,
    name: str = "Tau2 Thread",
    metadata: dict[str, Any] | None = None,
) -> str:
    threads_base = http_base.rstrip("/") + "/api/v2/threads"
    payload = {
        "name": name,
        "agent_id": agent_id,
        "messages": initial_messages or [],
        "metadata": metadata or {"source": "tau2"},
    }
    resp = _http_post_json(threads_base + "/", payload)
    thread_id = resp.get("thread_id")
    if not thread_id:
        raise RuntimeError("Thread creation failed: missing thread_id")
    return thread_id


def _make_initiate_stream_payload(
    agent_id: str,
    thread_id: str,
    client_tool_defs: list[dict[str, Any]],
    new_messages: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "agent_id": agent_id,
        "thread_id": thread_id,
        "messages": new_messages,
        "client_tools": client_tool_defs,
    }


def _make_client_tool_result(
    tool_call_id: str, output: Any, error: str | None = None
) -> dict[str, Any]:
    return {
        "event_type": "client_tool_result",
        "tool_call_id": tool_call_id,
        "result": {
            "output": output,
            "error": error,
        },
    }


# --------------------------
# State
# --------------------------


@dataclass
class Sema4AIState:
    # WebSocket connection + thread
    ws_url: str
    ws_app: Any | None = None
    ws_thread: threading.Thread | None = None
    ws_open_event: threading.Event = field(default_factory=threading.Event)

    # Queue of inbound events (already parsed JSON dicts)
    event_queue: "Queue[dict[str, Any]]" = field(default_factory=Queue)

    # Agent identifiers (set after 'agent_ready')
    run_id: str | None = None
    thread_id: str | None = None
    agent_id: str | None = None
    http_base_url: str | None = None

    # Connection flags
    connected: bool = False
    closed: bool = False
    close_reason: str | None = None

    # Buffer for streaming text
    current_text: str = ""

    # Structured accumulator for current streaming message
    current_message_obj: dict[str, Any] = field(default_factory=dict)

    # Pending client tool request metadata
    pending_tool_request: dict[str, Any] | None = None

    # Tool name -> Tool
    tools_index: dict[str, Tool] = field(default_factory=dict)


# --------------------------
# Utilities
# --------------------------


def _tool_to_client_def(tool: Tool) -> dict[str, Any]:
    try:
        schema = tool.params.model_json_schema()
    except Exception:
        schema = {"type": "object", "properties": {}}

    desc = tool.short_desc or tool.long_desc or tool.name
    return {
        "name": tool.name,
        "description": desc,
        "input_schema": schema,
        "category": "client-exec-tool",
    }


def _message_to_thread_text(role: str, text: str) -> dict[str, Any]:
    return {
        "role": role,  # 'user' | 'agent'
        "content": [{"kind": "text", "text": text}],
    }


def _translate_history_to_thread_messages(history: list[Message]) -> list[dict[str, Any]]:
    msgs: list[dict[str, Any]] = []
    for m in history:
        if isinstance(m, UserMessage) and (m.content and not m.is_tool_call()):
            msgs.append(_message_to_thread_text("user", m.content))
        elif isinstance(m, AssistantMessage) and (m.content and not m.is_tool_call()):
            msgs.append(_message_to_thread_text("agent", m.content))
    return msgs


def _decode_json_pointer_token(token: str) -> str:
    return token.replace("~1", "/").replace("~0", "~")


def _resolve_parent_and_key(doc: Any, path: str) -> tuple[Any, str | int]:
    if not path or path == "/":
        raise ValueError("Path must not point to the root document")
    tokens = [_decode_json_pointer_token(tok) for tok in path.split("/")[1:] if tok != ""]
    node: Any = doc
    for i, tok in enumerate(tokens[:-1]):
        next_tok = tokens[i + 1] if i + 1 < len(tokens) else None
        if isinstance(node, list):
            idx = int(tok) if tok.isdigit() else (len(node) if tok == "-" else None)
            if idx is None:
                raise ValueError(f"Invalid list token in path: {tok}")
            while idx >= len(node):
                node.append({})
            if node[idx] is None:
                node[idx] = {}
            node = node[idx]
        else:
            if tok not in node or node[tok] is None:
                node[tok] = [] if (next_tok is not None and next_tok.isdigit()) else {}
            node = node[tok]
    last = tokens[-1]
    if isinstance(node, list) and last.isdigit():
        return node, int(last)
    return node, last


def _apply_delta_to_object(doc: Any, delta: dict[str, Any]) -> Any:
    op = delta.get("op")
    path = delta.get("path", "")
    if op in {"add", "replace"} and (not path or path == "/"):
        value = delta.get("value")
        return value if value is not None else {}
    if op == "concat_string":
        parent, key = _resolve_parent_and_key(doc, path)
        try:
            current_value = parent[key]
        except Exception:
            current_value = None
        if current_value is None:
            current_value = ""
        if not isinstance(current_value, str):
            return doc
        parent[key] = current_value + (delta.get("value") or "")
        return doc
    try:
        patch = JsonPatch([delta])
        return patch.apply(doc)
    except (JsonPatchException, JsonPointerException, Exception) as e:
        logger.debug(f"Delta: {delta}")
        logger.debug(f"Doc: {doc}")
        logger.debug(f"Failed to apply delta via JsonPatch: {e}")
        return doc


def _extract_text_from_message_obj(message_obj: dict[str, Any]) -> str:
    try:
        content = message_obj.get("content", [])
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("kind") == "text":
                t = item.get("text")
                if isinstance(t, str):
                    parts.append(t)
        return "".join(parts)
    except Exception:
        return ""


def _apply_streaming_event(state: "Sema4AIState", event: dict[str, Any]) -> None:
    delta = event.get("delta") or {}
    if not isinstance(delta, dict):
        return
    if not state.current_message_obj:
        state.current_message_obj = {"role": "agent", "content": []}
    try:
        state.current_message_obj = _apply_delta_to_object(state.current_message_obj, delta)
        extracted = _extract_text_from_message_obj(state.current_message_obj)
        if extracted:
            state.current_text = extracted
    except Exception as e:
        logger.debug(f"Streaming event apply error: {e!r}")


# --------------------------
# WebSocket plumbing
# --------------------------


def _ws_on_open(state: "Sema4AIState"):
    def _inner(_: Any):
        logger.debug("WebSocket opened.")
        state.ws_open_event.set()

    return _inner


def _ws_on_message(state: "Sema4AIState"):
    def _inner(_: Any, message: str):
        try:
            payload = json.loads(message)
        except Exception:
            logger.debug("Non-JSON websocket frame ignored.")
            return
        state.event_queue.put(payload)

    return _inner


def _ws_on_error(state: "Sema4AIState"):
    def _inner(_: Any, error: Any):
        text = str(error)
        if "opcode=8" in text and ("\\x03\\xe8" in text or "1000" in text):
            logger.debug("WebSocket closed normally.")
        else:
            logger.error(f"WebSocket error: {error}")
        state.closed = True
        state.close_reason = f"WS error: {error!r}"

    return _inner


def _ws_on_close(state: "Sema4AIState"):
    def _inner(_: Any, status_code: Any, msg: Any):
        logger.debug(f"WebSocket closed: {status_code} {msg}")
        state.closed = True
        state.close_reason = f"WS closed: {status_code} {msg!r}"

    return _inner


def _reset_ws(state: Sema4AIState):
    """Tear down any prior socket and reset flags/queues for a fresh run."""
    try:
        if state.ws_app is not None:
            try:
                state.ws_app.close()
            except Exception:
                pass
    finally:
        state.ws_app = None
        state.ws_thread = None
        state.ws_open_event = threading.Event()
        state.event_queue = Queue()
        state.connected = False
        state.closed = False
        state.close_reason = "Reset WS"
        state.current_text = ""
        state.current_message_obj = {}
        state.pending_tool_request = None
        state.run_id = None


def _start_ws(state: Sema4AIState):
    if WebSocketApp is None:
        raise RuntimeError("websocket-client is required: pip install websocket-client")
    # Always create a new WS app for a new run
    ws_app = WebSocketApp(
        state.ws_url,
        on_open=_ws_on_open(state),
        on_message=_ws_on_message(state),
        on_error=_ws_on_error(state),
        on_close=_ws_on_close(state),
    )

    def _runner():
        if state.ws_app is None:
            raise RuntimeError("WebSocket not initialized")
        state.ws_app.run_forever(
            ping_interval=float(os.getenv("SEMA4AI_WS_PING_INTERVAL", "20")),
            ping_timeout=float(os.getenv("SEMA4AI_WS_PING_TIMEOUT", "10")),
        )

    state.ws_app = ws_app
    t = threading.Thread(target=_runner, daemon=True)
    t.start()
    state.ws_thread = t


def _ws_send_json(state: Sema4AIState, obj: dict[str, Any]):
    if state.ws_app is None:
        raise RuntimeError("WebSocket not initialized")
    try:
        state.ws_app.send(json.dumps(obj))
    except Exception as e:
        state.closed = True
        state.close_reason = f"WS send error: {e!r}"
        raise e


def _await_agent_ready(state: Sema4AIState, timeout: float = 15.0):
    """Wait for 'agent_ready' after initial payload."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            ev = state.event_queue.get(timeout=0.25)
        except Empty:
            continue
        if ev.get("event_type") == "agent_ready":
            state.run_id = ev.get("run_id")
            state.thread_id = ev.get("thread_id") or state.thread_id
            state.agent_id = ev.get("agent_id") or state.agent_id
            logger.debug(
                f"Agent ready: run={state.run_id}, thread={state.thread_id}, agent={state.agent_id}"
            )
            return
        else:
            # Not ready yet; buffer back (rare) so downstream can consume it
            state.event_queue.put(ev)
            time.sleep(0.05)
    raise TimeoutError("Timed out waiting for 'agent_ready' event.")


# --------------------------
# Agent Implementation
# --------------------------


class Sema4AIAgent(LLMAgent):
    """
    Tau2 LocalAgent that drives the Sema4AI standard WS endpoint with persistent agent/thread.

    Protocol (single turn):
      1) Ensure a persistent agent exists for this domain (by deterministic name)
      2) Ensure a persistent thread exists for that agent
      3) Open WS to /runs/{agent_id}/stream and send new user message
      4) Stream events until a 'decision':
            - request_tool_execution -> return ToolCall to Tau
            - agent_finished -> return assistant text
      5) While awaiting finish, if Tau returns ToolMessage(s),
         send client_tool_result over the SAME open WS
    """

    def __init__(  # noqa: PLR0913
        self,
        tools: list[Tool],
        domain_policy: str,
        *,
        ws_url: str | None = None,
        agent_name: str = "tau2",
        agent_description: str = "Tau2 persistent agent",
        task_id: str | None = None,
        platform_variant: str | None = None,
        domain_name: str | None = None,
        architecture_name: str | None = None,
    ):
        LocalAgent.__init__(self, tools=tools, domain_policy=domain_policy)
        self.ws_base = ws_url or DEFAULT_WS_BASE
        self.http_base = _ws_base_to_http_base(self.ws_base)
        self.agent_description = agent_description
        self.task_id = task_id
        self.domain_name = domain_name or os.getenv("TAU2_DOMAIN", "unknown")
        self.architecture_name = _normalize_architecture_name(architecture_name)
        # satisfy LLMAgent expectations even though we bypass its __init__
        self.llm = None
        self.llm_args: dict[str, Any] = {}

        # Parse platform/model from variant like "openai/gpt-4-1"
        platform_name: str | None = None
        model_name: str | None = None
        if platform_variant and isinstance(platform_variant, str):
            pv = platform_variant.strip()
            if pv:
                if "/" in pv:
                    platform_name, model_name = pv.split("/", 1)
                else:
                    platform_name = pv
        self.platform_override = platform_name.strip() if platform_name else None
        self.model_override = model_name.strip() if model_name else None

        # Compute agent name prefix, including platform/model for uniqueness if provided
        base_name = f"{agent_name}-{self.domain_name}"
        suffix_parts: list[str] = []
        if self.platform_override:
            suffix = self.platform_override
            if self.model_override:
                suffix = f"{suffix}-{self.model_override}"
            safe_suffix = suffix.replace("/", "-").replace(" ", "-")
            suffix_parts.append(safe_suffix)
        if self.architecture_name:
            suffix_parts.append(self.architecture_name.split(".")[-1])
        if suffix_parts:
            self.agent_name = f"{base_name}-{'-'.join(suffix_parts)}"
        else:
            self.agent_name = base_name

        # Precompute client tool definitions and name->Tool index
        self._client_tool_defs = [_tool_to_client_def(t) for t in tools]
        self._tools_index = {t.name: t for t in tools}

    # -------------
    # Base methods
    # -------------

    def get_init_state(self, message_history: list[Message] | None = None) -> Sema4AIState:
        return Sema4AIState(
            ws_url=self.ws_base,
            tools_index=self._tools_index.copy(),
            http_base_url=self.http_base,
        )

    def generate_next_message(  # noqa: C901, PLR0912
        self,
        message: ValidAgentInputMessage,
        state: Sema4AIState,
    ) -> tuple[AssistantMessage, Sema4AIState]:
        """
        Main turn handler.
        - For a UserMessage: ensure agent/thread, then stream this user msg.
        - For a ToolMessage/MultiToolMessage: send client_tool_result on the OPEN run.
        """
        try:
            if isinstance(message, UserMessage):
                if message.is_tool_call():
                    raise ValueError("UserMessage should not contain tool calls here.")
                if not message.content:
                    raise ValueError("UserMessage missing content.")

                # --- New turn: ensure persistent agent + thread, then stream THIS user message ---
                _reset_ws(state)

                # Ensure agent
                if not state.agent_id:
                    state.agent_id = _get_or_create_agent_id(
                        state.http_base_url or self.http_base,
                        self.domain_policy,
                        self._client_tool_defs,
                        self.agent_name,
                        self.agent_description,
                        platform=self.platform_override,
                        model=self.model_override,
                        architecture=self.architecture_name,
                    )

                # Ensure thread
                if not state.thread_id:
                    thread_name = "Tau2 Thread"
                    metadata = {"source": "tau2"}
                    if self.task_id:
                        thread_name = f"{thread_name} [{self.task_id}]"
                        metadata["task_id"] = self.task_id
                    state.thread_id = _create_thread(
                        state.http_base_url or self.http_base,
                        state.agent_id,
                        name=thread_name,
                        metadata=metadata,
                    )

                # Build WS URL for this agent
                state.ws_url = self.ws_base.rstrip("/") + f"/api/v2/runs/{state.agent_id}/stream"

                # Prepare this turn's message payload (only the new user message)
                new_user_msg = _message_to_thread_text("user", message.content)

                self._connect_and_seed(state, [new_user_msg])

                # Wait for the agent's next decision for THIS user message
                return self._wait_for_decision(state)

            elif isinstance(message, MultiToolMessage):
                # Continue an in-flight run: send each tool result in order
                if not state.connected or state.closed:
                    raise RuntimeError(
                        f"No active run to receive tool results: {state.close_reason}"
                    )
                for tm in message.tool_messages:
                    self._send_tool_result_to_server(tm, state)
                return self._wait_for_decision(state)

            elif isinstance(message, ToolMessage):
                if not state.connected or state.closed:
                    raise RuntimeError(
                        f"No active run to receive tool results: {state.close_reason}"
                    )
                self._send_tool_result_to_server(message, state)
                return self._wait_for_decision(state)

            else:
                raise ValueError(f"Unsupported message type: {type(message)}")
        except Exception as e:
            logger.error(f"Agent error: {e!r}")
            return AssistantMessage(role="assistant", content=f"(agent error) {e!r}"), state

    # -------------
    # Internals
    # -------------

    def _connect_and_seed(self, state: Sema4AIState, new_messages: list[dict[str, Any]]) -> None:
        """
        Start the WebSocket, send the initial payload for a persistent agent/thread,
        and wait for agent_ready.
        """
        _start_ws(state)

        # Wait for the socket to open before sending initial payload
        if not state.ws_open_event.wait(timeout=30.0):
            _reset_ws(state)
            raise TimeoutError(
                "Timed out waiting for WebSocket to open before sending initial payload."
            )

        payload = _make_initiate_stream_payload(
            agent_id=state.agent_id or "",
            thread_id=state.thread_id or "",
            client_tool_defs=self._client_tool_defs,
            new_messages=new_messages,
        )
        _ws_send_json(state, payload)

        # Wait for agent_ready
        _await_agent_ready(state, timeout=15.0)
        state.connected = True
        state.closed = False
        state.close_reason = "Connect and seed"
        state.current_text = ""
        state.pending_tool_request = None
        logger.debug("Initial payload sent and agent is ready.")

    def _wait_for_decision(  # noqa: C901, PLR0912, PLR0915
        self, state: Sema4AIState
    ) -> tuple[AssistantMessage, Sema4AIState]:
        """
        Consume events until either:
          - request_tool_execution -> return tool-call
          - agent_finished (with any text streamed) -> return assistant content
        """
        state.current_text = ""
        start = time.time()

        while True:
            if state.closed and state.event_queue.empty():
                reason = state.close_reason or "WebSocket closed unexpectedly."
                raise RuntimeError(
                    f"WebSocket closed before agent decision: {reason}",
                )
            # Timeout guard
            elapsed = time.time() - start
            if elapsed > MAX_ACCUM_SECONDS_FOR_PLAIN_ANSWER:
                raise TimeoutError("Timeout assembling agent response.")

            try:
                ev = state.event_queue.get(timeout=EVENT_POLL_TIMEOUT_SEC)
            except Empty as ex:
                if state.closed:
                    reason = state.close_reason or "WebSocket closed unexpectedly."
                    raise RuntimeError(
                        f"WebSocket closed before agent decision: {reason}",
                    ) from ex
                continue

            etype = ev.get("event_type")
            if etype == "message_begin":
                state.current_text = ""
                state.current_message_obj = {"role": "agent", "content": []}
                continue

            elif etype == "message_content":
                _apply_streaming_event(state, ev)
                continue

            elif etype == "agent_finished":
                final_text = state.current_text.strip()
                # Close the websocket after completing a user->agent turn
                try:
                    if state.ws_app is not None:
                        state.ws_app.close()
                except Exception:
                    pass
                finally:
                    state.connected = False
                    state.closed = True
                    state.close_reason = "Agent finished"
                    state.ws_app = None
                    state.ws_thread = None
                return AssistantMessage(role="assistant", content=final_text), state

            elif etype in ("request_tool_execution", "client_tool_request"):
                # Server asks us to run a client-side tool
                tool_name = ev.get("tool_name", "")
                tool_call_id = ev.get("tool_call_id", "")
                input_raw = ev.get("input_raw", "{}")
                args = json.loads(input_raw)

                state.pending_tool_request = {
                    "tool_name": tool_name,
                    "tool_call_id": tool_call_id,
                    "args": args,
                }

                tool_call = ToolCall(
                    id=tool_call_id,
                    name=tool_name or "",
                    arguments=args,
                    requestor="assistant",
                )
                return AssistantMessage(role="assistant", tool_calls=[tool_call]), state

            elif etype == "agent_error":
                details = ev.get("message") or ev.get("error_message") or "Agent error"
                logger.error(f"Agent error from server: {details}")
                return AssistantMessage(role="assistant", content=f"(agent error) {details}"), state

            elif etype in ("data", "agent_ready"):
                # Non-text side-channel or duplicate 'ready'
                continue

    def _send_tool_result_to_server(self, tool_msg: ToolMessage, state: Sema4AIState):
        """
        Send IncomingDeltaClientToolResult back to the agent-server for the
        tool request we previously surfaced as a Tau tool call.
        """
        tool_call_id = tool_msg.id
        raw = tool_msg.content
        try:
            output: Any = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            output = raw

        reply = _make_client_tool_result(tool_call_id=tool_call_id, output=output, error=None)
        _ws_send_json(state, reply)
        state.pending_tool_request = None

    def set_seed(self, seed: int):
        """LLMAgent compatibility shim; seed control handled upstream."""
        return None


# --------------------------
# Registration helpers
# --------------------------


_REGISTERED_SPECS: set[str] = set()


def _parse_agent_spec(agent_spec: str) -> tuple[str | None, str | None, str | None]:
    if not agent_spec:
        raise ValueError("Agent spec must be non-empty")
    prefix, _, rest = agent_spec.partition("/")
    if prefix != "sema4ai":
        raise ValueError(f"Unsupported agent prefix: {prefix}")
    if not rest:
        return None, None, None
    body, _, architecture_alias = rest.partition("@")
    platform, _, model = body.partition(":")
    platform = platform or None
    model = model or None
    architecture_alias = architecture_alias or None
    return platform, model, architecture_alias


def _sanitize_class_fragment(value: str) -> str:
    result = (
        value.replace("/", "_")
        .replace(":", "_")
        .replace("-", "_")
        .replace("@", "_")
        .replace("|", "_")
    )
    return "".join(ch for ch in result if ch.isalnum() or ch == "_")


def register_sema4ai_agent(agent_spec: str, *, ws_url: str | None = None) -> str:
    """Register a shim agent for the provided spec and return the registry key."""

    platform, model, architecture_alias = _parse_agent_spec(agent_spec)
    architecture_name = _normalize_architecture_name(architecture_alias)
    spec_key = f"{agent_spec}|{architecture_name}"
    if spec_key in _REGISTERED_SPECS:
        return agent_spec

    platform_variant: str | None = None
    if platform:
        platform_variant = f"{platform}/{model}" if model else platform

    description_suffix = platform_variant or "default"
    arch_label = architecture_alias or architecture_name.split(".")[-1]
    description_suffix = f"{description_suffix}-{arch_label}"
    resolved_ws = ws_url or os.getenv("SEMA4AI_BASE_URL", DEFAULT_WS_BASE)
    domain_name = os.getenv("TAU2_DOMAIN", "unknown")

    class _RegisteredSema4AIAgent(Sema4AIAgent):
        def __init__(self, tools: list[Tool], domain_policy: str, llm=None, llm_args=None):
            super().__init__(
                tools=tools,
                domain_policy=domain_policy,
                ws_url=resolved_ws,
                agent_name="tau2",
                agent_description=f"Tau2 agent ({description_suffix})",
                platform_variant=platform_variant,
                domain_name=domain_name,
                architecture_name=architecture_name,
            )

    safe_fragment = _sanitize_class_fragment(spec_key)
    _RegisteredSema4AIAgent.__name__ = f"Sema4AIAgent_{safe_fragment}"[:120]
    tau_registry.register_agent(_RegisteredSema4AIAgent, agent_spec)
    _REGISTERED_SPECS.add(spec_key)
    return agent_spec
