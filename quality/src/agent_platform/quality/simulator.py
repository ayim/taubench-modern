import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from agent_platform.quality.agent_client import (
    AgentClient,
    ClientTool,
    Tool,
    ToolDefinition,
    ToolExecutionResult,
    ToolExecutor,
)
from agent_platform.quality.conversation_judge import ConversationJudge, EvaluationResult
from agent_platform.quality.models import (
    AgentPackage,
    FileAttachment,
    Message,
    Platform,
    Text,
    Thought,
    ToolUse,
)
from agent_platform.quality.orchestrator import QualityOrchestrator

logger = structlog.get_logger(__name__)


@dataclass
class TraceEnvironment:
    name: str
    agent_name: str
    agent_server_version: str
    platform: str


@dataclass
class Trace:
    environment: TraceEnvironment
    messages: list[Message]
    tools: list[ToolDefinition]

    @classmethod
    def from_file(cls, file_path: Path) -> "Trace":
        """Load a trace from a YAML file."""
        import yaml

        with open(file_path) as f:
            data = yaml.safe_load(f)

        def parse_content(content: Any):
            if isinstance(content, str):
                return Text(content=content)

            kind = content["kind"]
            match kind:
                case "text":
                    return Text(content=content["text"])
                case "attachment":
                    return FileAttachment(
                        file_name=content["file_name"],
                        description=content["description"],
                        mime_type=content["mime_type"],
                    )
                case "thought":
                    return Thought(content=content["thought"])
                case "tool_use":
                    return ToolUse(
                        tool_name=content["tool_name"],
                        tool_call_id=content["tool_call_id"],
                        input_as_string=content["input_as_string"],
                        output_as_string=content["output_as_string"],
                        ended_at=content.get("ended_at"),
                        started_at=content.get("started_at"),
                        error=content.get("error", None),
                    )

            raise ValueError(f"Unknown message content kind {kind}")

        messages = [
            Message(
                role=msg["role"], content=[parse_content(content) for content in msg["content"]]
            )
            for msg in data["messages"]
        ]

        environment_data = data.get("environment", None)
        environment = TraceEnvironment(
            agent_name=environment_data.get("agent_name"),
            agent_server_version=environment_data.get("agent_server_version"),
            name=environment_data.get("name"),
            platform=environment_data.get("platform"),
        )

        tools_data = data.get("tools", [])
        tools = [
            ToolDefinition(
                name=tool_data.get("name"),
                description=tool_data.get("description"),
                input_schema=tool_data.get("input_schema"),
            )
            for tool_data in tools_data
        ]

        return cls(environment, messages, tools)


@dataclass
class ReplayResult:
    golden_trace: Trace
    success: bool
    evaluation_results: list[EvaluationResult]
    trace: Trace | None = None
    error: str | None = None


@dataclass
class _ExpectedCall:
    tool_name: str
    expected_args: dict[str, Any]
    output: dict[str, Any]
    error: str | None = None


class ReplayToolExecutor(ToolExecutor):
    """
    Replays tool calls from a captured conversation.
    Enforces both call order and argument equality (deep compare).
    """

    def __init__(self, expected_calls: list[_ExpectedCall], *, strict_args: bool = True):
        self._calls = expected_calls
        self._i = 0
        self._strict = strict_args

    @classmethod
    def from_conversation(cls, trace: Trace) -> "ReplayToolExecutor":
        """
        Build a ReplayToolExecutor from the provided YAML (already parsed as a Python dict).

        It looks for content items with:
          - kind: "tool_use"
          - fields: tool_name, input_as_string (JSON), output_as_string (JSON)
        """
        expected: list[_ExpectedCall] = []

        for msg in trace.messages:
            for item in msg.content:
                if isinstance(item, ToolUse):
                    tool_name = item.tool_name
                    # Inputs/outputs are JSON strings in the provided log.
                    raw_in = item.input_as_string
                    raw_out = item.output_as_string

                    try:
                        expected_args = json.loads(raw_in)
                    except json.JSONDecodeError as e:
                        raise ValueError(f"Bad input JSON for {tool_name}: {e}\n{raw_in}") from e

                    try:
                        output = json.loads(raw_out)
                    except json.JSONDecodeError as e:
                        raise ValueError(f"Bad output JSON for {tool_name}: {e}\n{raw_out}") from e

                    expected.append(_ExpectedCall(tool_name, expected_args, output, item.error))

        return cls(expected)

    def _assert_next(self, tool: Tool) -> _ExpectedCall:
        if self._i >= len(self._calls):
            raise AssertionError(
                f"Unexpected tool call #{self._i + 1}: {tool.tool_name}. "
                "No more calls were recorded."
            )

        exp = self._calls[self._i]

        if tool.tool_name != exp.tool_name:
            raise AssertionError(
                f"Tool name mismatch at call #{self._i + 1}.\n"
                f"  expected: {exp.tool_name}\n"
                f"  got     : {tool.tool_name}"
            )

        try:
            actual_args = json.loads(tool.input_raw)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Bad actual input JSON for {tool.tool_name}: {e}\n{tool.input_raw}"
            ) from e

        # Args check (deep equality). If needed, you can customize to allow
        # reordering or extra keys using self._strict.
        if self._strict:
            if actual_args != exp.expected_args:
                raise AssertionError(
                    f"Arguments mismatch at call #{self._i + 1} for '{tool.tool_name}'.\n"
                    f"  expected args: {json.dumps(exp.expected_args, indent=2, sort_keys=True)}\n"
                    f"  got args     : {json.dumps(actual_args, indent=2, sort_keys=True)}"
                )
        else:
            # Non-strict: ensure all expected keys match and values are equal.
            for k, v in exp.expected_args.items():
                if k not in tool.input_raw or actual_args[k] != v:
                    raise AssertionError(
                        f"Non-strict arg mismatch at call #{self._i + 1} for '{tool.tool_name}'. "
                        f"Key '{k}' expected value {v}, got {actual_args.get(k, '<missing>')}"
                    )

        return exp

    async def execute(self, tool: Tool) -> ToolExecutionResult:
        exp = self._assert_next(tool)
        self._i += 1
        return ToolExecutionResult(error=exp.error, output=json.dumps(exp.output))

    def assert_all_consumed(self) -> None:
        """Optional: call at the end of a test to ensure no missing calls."""
        if self._i != len(self._calls):
            remaining = len(self._calls) - self._i
            raise AssertionError(f"{remaining} recorded tool call(s) were not executed.")


def sublist_until_last(
    messages: list["Message"], condition: Callable[["Message"], bool]
) -> list["Message"]:
    """
    Returns a slice of `messages` starting at index 0 and ending at the last element
    that satisfies `condition` (inclusive).
    If no element matches, returns an empty list.
    """
    last_index = None
    for i, msg in enumerate(messages):
        if condition(msg):
            last_index = i

    if last_index is None:
        return []
    return messages[: last_index + 1]


class ReplayResultManager:
    def __init__(self, datadir: Path):
        self.datadir = datadir
        self.results_dir = datadir / "replay_results"
        self.runs_dir = self.results_dir / "runs"

        self.current_run_id = datetime.now().strftime("run_%Y-%m-%d_%H-%M-%S")
        self.current_run_dir = self.runs_dir / self.current_run_id

        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self.current_run_dir.mkdir(parents=True, exist_ok=True)

    def save_result(self, result: ReplayResult):
        # TODO it is not clear what name we should choose in a unique way
        replay_result_file = self.current_run_dir / "replay_result.json"

        with open(replay_result_file, "w") as f:
            payload = {
                "success": result.success,
                "error": result.error,
                "golden_trace": self._get_trace_as_json(result.golden_trace),
                "trace": self._get_trace_as_json(result.trace)
                if result.trace is not None
                else None,
                "evaluations": [self._get_eval_as_json(e) for e in result.evaluation_results],
            }
            json.dump(payload, f, indent=4)

    def _get_eval_as_json(self, evaluation: EvaluationResult):
        data = {
            "passed": evaluation.passed,
            "value": evaluation.value,
            "error": evaluation.error,
        }

        return data

    def _get_trace_as_json(self, trace: Trace):
        environment = {
            "name": trace.environment.name,
            "agent_name": trace.environment.agent_name,
            "agent_server_version": trace.environment.agent_server_version,
            "platform": trace.environment.platform,
        }
        tools = []
        for t in trace.tools:
            tools.append(
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema,
                }
            )

        def message_to_export(m: Message) -> dict:
            items = []
            for it in m.content:
                if isinstance(it, Thought):
                    items.append({"type": "thought", "thought": it.content})
                elif isinstance(it, Text):
                    items.append({"type": "text", "text": it.content})
                elif isinstance(it, ToolUse):
                    tool_obj = {
                        "type": "tool_use",
                        "tool_name": it.tool_name,
                        "tool_call_id": it.tool_call_id,
                        "input_as_string": it.input_as_string,
                        "output_as_string": it.output_as_string,
                        "started_at": it.started_at,
                        "ended_at": it.ended_at,
                    }
                    if it.error is not None:
                        tool_obj["error"] = it.error
                    items.append(tool_obj)
                else:
                    raise TypeError(f"Unsupported content item: {type(it).__name__}")
            return {"content": items, "role": m.role}

        messages = [message_to_export(m) for m in trace.messages]

        return {"environment": environment, "tools": tools, "messages": messages}


class Simulator:
    def __init__(
        self,
        test_threads_dir: Path,
        test_agents_dir: Path,
        server_url: str,
        datadir: Path,
        agent_server_version: str | None = None,
    ):
        self.test_threads_dir = test_threads_dir
        self.test_agents_dir = test_agents_dir
        self.server_url = server_url

        self.orchestrator = QualityOrchestrator(
            server_url=server_url,
            data_dir=datadir,
            agent_server_version=None if agent_server_version == "latest" else agent_server_version,
        )

        self.result_manager = ReplayResultManager(datadir=datadir)

    async def replay_trace(
        self,
        golden_trace: Trace,
        assert_all_consumed: bool = False,
        agent_server_version: str | None = None,
        platform: str | None = None,
        agent_name: str | None = None,
    ):
        agents = self._discover_agents()
        if not agents:
            raise RuntimeError("No agent packages found")

        agents = [agent for agent in agents if agent.name == golden_trace.environment.agent_name]

        if len(agents) == 0:
            raise RuntimeError(f"No agent with name {golden_trace.environment.agent_name}")

        infrastructure_started = False

        agent = agents[0]

        new_environment = TraceEnvironment(
            name=f"Replay {golden_trace.environment.name}",
            agent_name=agent_name
            if agent_name is not None
            else golden_trace.environment.agent_name,
            agent_server_version=agent_server_version
            if agent_server_version is not None
            else golden_trace.environment.agent_server_version,
            platform=platform if platform is not None else golden_trace.environment.platform,
        )

        try:
            agent_server_url = await self.orchestrator.start_infrastructure()
            infrastructure_started = True

            agent_id = await self.orchestrator._upload_agent_with_platform(
                agent_zip_path=agent.zip_path,
                agent_name=agent.name,
                platform=Platform(name=new_environment.platform),
            )

            tool_executor = ReplayToolExecutor.from_conversation(golden_trace)
            client_tools = [
                ClientTool(
                    name=tool.name, description=tool.description, input_schema=tool.input_schema
                )
                for tool in golden_trace.tools
            ]
            agent = AgentClient(
                thread_name="Testing websockets",
                agent_id=agent_id,
                agent_server_base_url=agent_server_url,
                tools=client_tools,
                tool_executor=tool_executor,
            )

            # TODO for now we consider a single turn conversation: user request/agent response
            initial_payload = sublist_until_last(golden_trace.messages, lambda m: m.role == "user")

            agent_messages = []
            try:
                # TODO get messages in a stream-y way
                new_agent_messages = await agent.run_once(initial_payload)
                agent_messages.extend(new_agent_messages)

                if assert_all_consumed:
                    tool_executor.assert_all_consumed()

                trace = Trace(
                    environment=new_environment,
                    tools=golden_trace.tools,
                    messages=initial_payload + agent_messages,
                )
                judge = ConversationJudge(agent_server_url=self.server_url)

                evaluation = await judge.evaluate(
                    benchmark=golden_trace.messages, target=trace.messages
                )
                result = ReplayResult(
                    trace=trace,
                    golden_trace=golden_trace,
                    success=True,
                    evaluation_results=[evaluation],
                )
                self.result_manager.save_result(result)

                return result
            except AssertionError as e:
                new_agent_messages = agent.get_messages()
                agent_messages.extend(new_agent_messages)
                trace = Trace(
                    environment=new_environment,
                    tools=golden_trace.tools,
                    messages=initial_payload + agent_messages,
                )
                result = ReplayResult(
                    golden_trace=golden_trace,
                    trace=trace,
                    success=False,
                    error=f"{e}",
                    # TODO it would be nice to add assert errors
                    evaluation_results=[],
                )

                self.result_manager.save_result(result)

                return result
        finally:
            if infrastructure_started:
                logger.info("Stopping shared infrastructure")
                await self.orchestrator.stop_infrastructure()

    def _discover_agents(self) -> list[AgentPackage]:
        """Discover available agent packages."""
        logger.info(f"Discovering agents in {self.test_agents_dir}")

        agents = []
        for zip_path in self.test_agents_dir.glob("*.zip"):
            name = zip_path.stem
            agents.append(
                AgentPackage(
                    name=name,
                    path=self.test_agents_dir / name,
                    zip_path=zip_path,
                )
            )

        logger.info(f"Found {len(agents)} agent packages")
        return agents
