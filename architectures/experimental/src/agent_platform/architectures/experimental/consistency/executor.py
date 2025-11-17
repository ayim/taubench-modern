import json
import logging
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from typing import Annotated, Any

from agent_platform.architectures.experimental.consistency.prompts import build_prompt
from agent_platform.architectures.experimental.consistency.resolution import blocked_resolution
from agent_platform.architectures.experimental.consistency.state import (
    ConsistencyArchState,
    MonitorFeedbackEntry,
)
from agent_platform.architectures.experimental.consistency.state_utils import (
    StateSync,
    set_plan_execution_phase_fields,
    sync_consistency_metadata,
)
from agent_platform.architectures.experimental.consistency.streaming import (
    PIPE_FINAL_REPLY,
    PIPE_TOOL_LOOP,
    stream_with_retry,
)
from agent_platform.architectures.experimental.consistency.tools_registry import ToolsRegistry
from agent_platform.core import Kernel
from agent_platform.core.kernel_interfaces.model_platform import PlatformInterface
from agent_platform.core.kernel_interfaces.thread_state import ThreadMessageWithThreadState
from agent_platform.core.prompts.prompt import Prompt
from agent_platform.core.responses import ResponseMessage, ResponseToolUseContent
from agent_platform.core.responses.streaming.stream_pipe import ResponseStreamPipe
from agent_platform.core.tools.tool_definition import ToolDefinition
from agent_platform.core.tools.tool_execution_result import ToolExecutionResult

logger = logging.getLogger(__name__)

# ---- Architecture knobs -------------------------------------------------------

MAX_ITERATIONS = 25
NO_TOOLCALL_RETRY_LIMIT = 3
NO_FINAL_REPLY_RETRY_LIMIT = 3


class PlanExecutor:
    def __init__(
        self,
        kernel: Kernel,
        platform: PlatformInterface,
        model: str,
        state: ConsistencyArchState,
        message: ThreadMessageWithThreadState,
    ):
        self.kernel = kernel
        self.platform = platform
        self.model = model
        self.state = state
        self.message = message
        self.registry = ToolsRegistry(kernel, state)

    # ---- Orchestration -------------------------------------------------------

    async def run(self) -> None:
        # gather tools + ensure plan
        with_phase = StateSync(self.state, self.message)
        async with with_phase:
            tools, issues = await self.registry.gather(self.message, refresh=True)
            self.state.configuration_issues = issues
            self.state.available_tools_markdown = self.registry.format_for_prompt(tools)
            set_plan_execution_phase_fields(
                self.state,
                phase="planning",
                caption="Generating the plan...",
            )

        await self._ensure_plan_initialized()

        if not self.state.plan_steps:
            await self._final_reply()
            return

        await self._execute_steps()
        await self._final_reply()

    # ---- Planning ------------------------------------------------------------

    async def _ensure_plan_initialized(self) -> None:
        """
        Ensure a plan exists by invoking the plan-creation prompt with consistency tools.
        """
        if self.state.plan_steps:
            # Snapshot is produced by sync_consistency_metadata, which we call often.
            return

        try:
            plan_prompt = await build_prompt(
                kernel=self.kernel,
                state=self.state,
                prompt_path="prompts/plan-creation",
                tools=self.state.consistency_tools,
                tool_choice="any",
            )
        except Exception:
            logger.exception("Failed to format plan-creation prompt.")
            await sync_consistency_metadata(self.state, self.message)
            return

        try:
            await self._invoke_consistency_prompt(
                prompt=plan_prompt,
                tool_definitions=self.state.consistency_tools,
                call_type="consistency-plan",
            )
        except Exception:
            logger.exception("Planning prompt execution failed.")

        # Assess plan result
        if not self.state.plan_steps:
            # Fail the plan with actionable guidance and surface a monitor entry.
            failure_message = (
                "Planning assistant did not register a plan. Start your next turn by drafting a "
                "Runbook-aligned plan before calling other tools."
            )
            self.state.plan_status = "failed"
            self.state.plan_failure_reason = failure_message
            self.state.plan_failure_level = "critical"

            timestamp = _now_iso()
            failure_entry = MonitorFeedbackEntry(
                timestamp=timestamp,
                message=failure_message,
                level="critical",
                related_steps=[],
            )
            self.state.monitor_feedback_latest = failure_entry
            self.state.monitor_feedback_history.append(failure_entry)
            self.state.monitor_feedback_pending.append(failure_entry)
            await sync_consistency_metadata(self.state, self.message)
            logger.warning("Planning prompt completed without registering any plan steps.")
        else:
            logger.info(
                "Planning prompt registered plan with %s steps. First title: %s",
                len(self.state.plan_steps),
                self.state.plan_steps[0].title if self.state.plan_steps else "<none>",
            )

    # ---- Step execution loop -------------------------------------------------

    async def _execute_steps(self) -> None:
        set_plan_execution_phase_fields(
            self.state,
            phase="executing-step",
            caption="Executing plan steps...",
        )
        await sync_consistency_metadata(self.state, self.message)

        while (idx := _next_plan_step_index(self.state)) is not None:
            resolution, recent_results = await self._execute_single_step(idx)

            # Monitor phase
            set_plan_execution_phase_fields(
                self.state,
                phase="monitoring",
                caption="Evaluating recent work...",
            )
            await sync_consistency_metadata(self.state, self.message)
            await self._run_monitor(recent_results)

            # Merge monitor feedback into controller feedback
            _merge_monitor_feedback(self.state)

            # Handle rework requests
            if self.state.rework_requested_for_step_id:
                rework_id = self.state.rework_requested_for_step_id
                try:
                    _ = next(
                        i for i, s in enumerate(self.state.plan_steps) if s.step_id == rework_id
                    )
                except StopIteration:
                    logger.error("Rework requested for unknown step_id: %s", rework_id)
                    self.state.rework_requested_for_step_id = None
                else:
                    # Reset execution pointers; loop continues and picks the next pending step.
                    self.state.rework_requested_for_step_id = None
                    self.state.current_plan_step_id = None
                    self.state.current_plan_step_index = -1
                    self.state.current_step_resolution = None
                    set_plan_execution_phase_fields(
                        self.state,
                        phase="executing-step",
                        caption="Executing plan steps...",
                    )
                    await sync_consistency_metadata(self.state, self.message)
                    continue

            # Exit conditions
            if self.state.plan_status == "failed":
                logger.warning("Plan marked as failed; terminating execution loop.")
                break
            if resolution.get("status") == "blocked":
                logger.warning(
                    "Plan execution halted after step %s due to blocked status.",
                    resolution.get("step_id"),
                )
                if self.state.plan_status != "failed":
                    self.state.plan_status = "failed"
                    self.state.plan_failure_reason = (
                        resolution.get("note", "Plan blocked without detail.") or ""
                    )
                    self.state.plan_failure_level = resolution.get("level", "warning") or "warning"
                break

            set_plan_execution_phase_fields(
                self.state,
                phase="executing-step",
                caption="Executing plan steps...",
            )
            await sync_consistency_metadata(self.state, self.message)

        set_plan_execution_phase_fields(
            self.state,
            phase="finalizing",
            caption="Preparing final response...",
        )
        await sync_consistency_metadata(self.state, self.message)

    async def _execute_single_step(  # noqa: C901, PLR0915
        self, index: int
    ) -> tuple[dict[str, Any], list[ToolExecutionResult]]:
        step = self.state.plan_steps[index]
        self.state.current_plan_step_index = index
        self.state.current_plan_step_id = step.step_id
        self.state.current_step_resolution = None
        set_plan_execution_phase_fields(
            self.state,
            phase="executing-step",
            caption=f"Executing plan step {index + 1}...",
        )
        self.state.no_toolcall_retry_count = 0
        self.state.current_iteration = 0

        if step.status != "in_progress":
            step.status = "in_progress"
            step.last_updated = _now_iso()

        await sync_consistency_metadata(self.state, self.message)

        loop_attempts = 0
        recent_results: list[ToolExecutionResult] = []

        while self.state.current_step_resolution is None:
            loop_attempts += 1
            self.state.current_iteration = loop_attempts

            tools_bundle, issues = await self.registry.gather(
                self.message, refresh=(loop_attempts == 1)
            )
            self.state.configuration_issues = issues
            _update_elapsed_time(self.state)

            logger.info(
                "Executing plan step %s/%s (%s) iteration=%s",
                index + 1,
                len(self.state.plan_steps),
                step.step_id,
                loop_attempts,
            )

            # Build a tool-loop prompt with consistency + support tools
            support_tools = self._execution_support_tools()
            conversation_prompt = await build_prompt(
                kernel=self.kernel,
                state=self.state,
                prompt_path="prompts/tool-loop",
                tools=_execution_tool_list(
                    tools_bundle, (*self.state.consistency_tools, *support_tools)
                ),
            )

            # Stream and collect any pending tool calls
            await stream_with_retry(
                platform=self.platform,
                model=self.model,
                prompt=conversation_prompt,
                message=self.message,
                state=self.state,
                spec=PIPE_TOOL_LOOP,
            )

            pending = list(self.state.pending_tool_calls)
            if not pending:
                self.state.no_toolcall_retry_count += 1
                if self.state.no_toolcall_retry_count <= NO_TOOLCALL_RETRY_LIMIT:
                    remaining = NO_TOOLCALL_RETRY_LIMIT - self.state.no_toolcall_retry_count
                    self.state.controller_feedback = (
                        f"No tool calls were detected for step '{step.step_id}' "
                        f"('{step.title}'). This is a TOOL-ONLY turn. "
                        f"Call a tool aligned with the step or block_current_step(...). "
                        f"Retries remaining: {remaining}."
                    )
                    logger.warning(
                        "No tool calls detected for step %s; retrying (%s/%s).",
                        step.step_id,
                        self.state.no_toolcall_retry_count,
                        NO_TOOLCALL_RETRY_LIMIT,
                    )
                    await sync_consistency_metadata(self.state, self.message)
                    continue

                resolution = blocked_resolution(
                    step,
                    index,
                    "No tool calls produced for this step despite retries.",
                    level="warning",
                )
                self.state.current_step_resolution = resolution
                self.state.controller_feedback = ""
                await sync_consistency_metadata(self.state, self.message)
                logger.warning(
                    "Plan step %s blocked due to repeated lack of tool calls.", step.step_id
                )
                break

            self.state.no_toolcall_retry_count = 0
            self.state.controller_feedback = ""

            await _mark_tools_running(self.message, self.state.pending_tool_calls)
            recent_results = await _execute_pending_tools(self.kernel, self.state, self.message)
            self.state.pending_tool_calls.clear()

            if self.state.plan_status == "failed":
                if step.status == "in_progress":
                    step.status = "blocked"
                    step.last_updated = _now_iso()
                    if self.state.plan_failure_reason:
                        step.notes.append(
                            {
                                "timestamp": _now_iso(),
                                "note": self.state.plan_failure_reason,
                                "level": self.state.plan_failure_level or "critical",
                            }
                        )
                self.state.current_step_resolution = {
                    "status": "blocked",
                    "note": self.state.plan_failure_reason or "Plan was declared failed.",
                    "level": self.state.plan_failure_level or "critical",
                    "timestamp": _now_iso(),
                    "step_id": step.step_id,
                    "index": index,
                }
                await sync_consistency_metadata(self.state, self.message)
                logger.warning(
                    "Plan step %s halted because the plan was declared failed.", step.step_id
                )
                break

            if not recent_results:
                resolution = blocked_resolution(
                    step,
                    index,
                    "Model failed to execute any tools for the current step.",
                    level="warning",
                )
                self.state.current_step_resolution = resolution
                await sync_consistency_metadata(self.state, self.message)
                logger.warning(
                    "Plan step %s blocked because no tools were executed despite pending calls.",
                    step.step_id,
                )
                break

            # If a tool resolved the step, we're done.
            if self.state.current_step_resolution is not None:
                logger.info(
                    "Plan step %s resolved via tool call: %s",
                    step.step_id,
                    self.state.current_step_resolution,
                )
                break

            if loop_attempts >= MAX_ITERATIONS:
                resolution = blocked_resolution(
                    step,
                    index,
                    "Reached iteration limit for this plan step.",
                    level="warning",
                )
                self.state.current_step_resolution = resolution
                await sync_consistency_metadata(self.state, self.message)
                logger.warning("Plan step %s blocked due to iteration limit.", step.step_id)
                break

            await sync_consistency_metadata(self.state, self.message)

        resolution = self.state.current_step_resolution or {
            "status": step.status,
            "note": "",
            "level": "info",
            "timestamp": _now_iso(),
            "step_id": step.step_id,
            "index": index,
        }

        self.state.last_step_resolution = resolution
        self.state.current_step_resolution = None
        self.state.step = "processing"
        return resolution, recent_results

    # ---- Monitor -------------------------------------------------------------

    async def _run_monitor(self, recent_results: Sequence[ToolExecutionResult]) -> None:
        if not recent_results:
            return

        self.state.latest_tool_events_markdown = _summarize_tool_results(recent_results)

        monitor_prompt = await build_prompt(
            kernel=self.kernel,
            state=self.state,
            prompt_path="prompts/monitor-progress",
            tools=self.state.consistency_tools,
            tool_choice="any",
        )

        try:
            await self._invoke_consistency_prompt(
                prompt=monitor_prompt,
                tool_definitions=self.state.consistency_tools,
                call_type="consistency-monitor",
            )
        except Exception:
            logger.exception("Monitor prompt execution failed.")

    # ---- Final reply ---------------------------------------------------------

    def _stage_for_final_reply_tool(self) -> ToolDefinition:
        async def _stage_for_final_reply_internal(
            content: Annotated[str, "The content of the artifact to be staged."],
            description: Annotated[str, "The description of the artifact to be staged."],
        ) -> dict[str, str]:
            self.state.staged_for_final_reply.append(
                {"content": content, "description": description}
            )
            logger.info("Staged artifact for final reply: %s", description)
            return {"result": f"Successfully staged artifact: {description}"}

        return ToolDefinition.from_callable(
            _stage_for_final_reply_internal, name="stage_for_final_reply"
        )

    async def _final_reply(self) -> None:
        # Prepare staged artifacts as markdown for the final prompt
        if self.state.staged_for_final_reply:
            lines = []
            for idx, artifact in enumerate(self.state.staged_for_final_reply, 1):
                desc = artifact.get("description", "No description")
                content = artifact.get("content", "")
                lines.append(f"### Artifact {idx}: {desc}")
                lines.append("```")
                lines.append(content)
                lines.append("```")
            self.state.staged_artifacts_markdown = "\n".join(lines)
        else:
            self.state.staged_artifacts_markdown = "No artifacts were staged during plan execution."

        has_final_reply = False
        self.state.no_final_reply_retry_count = 0
        while not has_final_reply:
            final_prompt = await build_prompt(
                kernel=self.kernel,
                state=self.state,
                prompt_path="prompts/final-reply",
                minimize_reasoning=True,
            )
            logger.info(
                "Producing final reply (attempt %s)", self.state.no_final_reply_retry_count + 1
            )
            stream = await stream_with_retry(
                platform=self.platform,
                model=self.model,
                prompt=final_prompt,
                message=self.message,
                state=self.state,
                spec=PIPE_FINAL_REPLY,
            )
            has_final_reply = _has_text_content(stream)
            if not has_final_reply:
                if not await _handle_no_final_reply(self.state, self.message):
                    break
        # Do not commit here; outer entrypoint commits the message.

    # ---- Consistency prompt helper ------------------------------------------

    async def _invoke_consistency_prompt(
        self,
        *,
        prompt: Prompt,
        tool_definitions: Sequence[ToolDefinition],
        call_type: str,
    ) -> ResponseMessage:
        response = await self.platform.generate_response(prompt, self.model)
        await _execute_consistency_tool_calls(self.kernel, response, tool_definitions)
        _record_model_call_metadata(
            message=self.message,
            platform_name=self.platform.name,
            model=self.model,
            call_type=call_type,
            response=response,
        )
        return response

    # ---- Tools for the execution loop ---------------------------------------

    def _execution_support_tools(self) -> list[ToolDefinition]:
        """
        Returns tools that support the execution flow (e.g., staging artifacts).
        """

        return [self._stage_for_final_reply_tool()]


# ---- Helpers -----------------------------------------------------------------


def _next_plan_step_index(state: ConsistencyArchState) -> int | None:
    for index, step in enumerate(state.plan_steps):
        if step.status in {"pending", "in_progress"}:
            return index
    return None


def _execution_tool_list(
    tools,
    extra: Sequence[ToolDefinition],
) -> list[ToolDefinition]:
    extra_names = {tool.name for tool in extra}
    filtered = [tool for tool in tools if tool.name not in extra_names]
    return [*filtered, *extra]


async def _mark_tools_running(
    message: ThreadMessageWithThreadState,
    pending_tool_calls: Iterable[tuple[ToolDefinition, ResponseToolUseContent]],
) -> None:
    pending_list = list(pending_tool_calls)
    logger.info("Pending tool calls: %s", len(pending_list))
    for _, tool_call in pending_list:
        message.update_tool_running(tool_call.tool_call_id)
    await message.stream_delta()


async def _execute_pending_tools(
    kernel: Kernel,
    state: ConsistencyArchState,
    message: ThreadMessageWithThreadState,
) -> list[ToolExecutionResult]:
    recent: list[ToolExecutionResult] = []
    async for result in kernel.tools.execute_pending_tool_calls(state.pending_tool_calls, message):
        recent.append(result)

    return recent


def _merge_monitor_feedback(state: ConsistencyArchState) -> None:
    if not state.monitor_feedback_pending:
        return
    lines: list[str] = []
    for entry in state.monitor_feedback_pending:
        msg = (entry.get("message") or "").strip()
        if not msg:
            continue
        level = (entry.get("level") or "info").upper()
        related = entry.get("related_steps") or []
        prefix = f"[{level}]"
        if related:
            prefix = f"{prefix} steps: {', '.join(related)}"
        lines.append(f"{prefix} {msg}")
    if not lines:
        state.monitor_feedback_pending.clear()
        return
    combined = "\n".join(lines)
    state.controller_feedback = (
        f"{combined}\n\n{state.controller_feedback}" if state.controller_feedback else combined
    )
    state.monitor_feedback_pending.clear()


def _summarize_tool_results(results: Sequence[ToolExecutionResult]) -> str:
    if not results:
        return "No tool calls executed."
    lines: list[str] = []
    for r in results:
        status = "error" if r.error else "ok"
        lines.append(f"- {r.definition.name} (status: {status})")
        lines.append(f"  input: {_safe_json_dump(r.input, limit=400)}")
        if r.error:
            lines.append(f"  error: {_truncate(r.error, limit=300)}")
        else:
            lines.append(f"  output: {_safe_json_dump(r.output_raw, limit=600)}")
    return "\n".join(lines)


def _safe_json_dump(value: Any, *, limit: int) -> str:
    if value is None:
        return "null"
    try:
        serialized = json.dumps(value, ensure_ascii=True)
    except TypeError:
        serialized = str(value)
    return _truncate(serialized, limit=limit)


def _truncate(text: str, *, limit: int) -> str:
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _update_elapsed_time(state: ConsistencyArchState) -> None:
    elapsed_seconds = (
        datetime.now(UTC) - datetime.fromisoformat(state.processing_start_time)
    ).total_seconds()
    state.processing_elapsed_time = f"{elapsed_seconds:.2f} seconds"


async def _execute_consistency_tool_calls(
    kernel: Kernel,
    response: ResponseMessage,
    tool_definitions: Sequence[ToolDefinition],
) -> None:
    tool_index = {definition.name: definition for definition in tool_definitions}
    pending_calls: list[tuple[ToolDefinition, ResponseToolUseContent]] = []
    for content in response.content:
        if isinstance(content, ResponseToolUseContent):
            tool_def = tool_index.get(content.tool_name)
            if not tool_def:
                logger.warning(
                    "Consistency prompt emitted unknown tool '%s'; ignoring.", content.tool_name
                )
                continue
            pending_calls.append((tool_def, content))

    if not pending_calls:
        logger.warning(
            "Consistency prompt completed without any tool calls. First response fragment: %s",
            getattr(response, "content", None),
        )
        return

    async for result in kernel.tools.execute_pending_tool_calls(pending_calls):
        logger.info(
            "Consistency tool executed: name=%s error=%s duration_ms=%.2f",
            result.definition.name,
            bool(result.error),
            (result.execution_ended_at - result.execution_started_at).total_seconds() * 1000,
        )


def _record_model_call_metadata(
    message: ThreadMessageWithThreadState,
    platform_name: str,
    model: str,
    call_type: str,
    response: ResponseMessage,
) -> None:
    usage_payload = None
    try:
        usage_payload = response.usage.model_dump()
    except Exception:
        pass
    message.agent_metadata.setdefault("models", [])
    message.agent_metadata["models"].append(
        {
            "platform": platform_name,
            "model": model,
            "call_type": call_type,
            "usage": usage_payload,
        }
    )


def _has_text_content(stream: ResponseStreamPipe | None) -> bool:
    """
    Determine if the final reply produced any non-empty text.
    Uses stream.reassembled_response.content when available.
    """
    from agent_platform.core.responses.content.text import ResponseTextContent

    if not stream or not stream.reassembled_response:
        return False
    content = stream.reassembled_response.content
    if not content:
        return False
    return any(isinstance(c, ResponseTextContent) and c.text.strip() for c in content)


async def _handle_no_final_reply(
    state: ConsistencyArchState, message: ThreadMessageWithThreadState
) -> bool:
    state.no_final_reply_retry_count += 1
    if state.no_final_reply_retry_count <= NO_FINAL_REPLY_RETRY_LIMIT:
        state.controller_feedback = (
            "No text was produced in the final reply, text MUST be provided to the user. "
            "This is a FINAL-REPLY-ONLY turn. All tool calls will be ignored. "
            "Please provide a text-only final reply, according to your instructions."
        )
        logger.info(
            "Final reply contained no text or attempted tool use; retrying (%s/%s).",
            state.no_final_reply_retry_count,
            NO_FINAL_REPLY_RETRY_LIMIT,
        )
        return True
    logger.info("No final reply after retries; failing open with placeholder.")
    state.step = "done"
    state.controller_feedback = ""
    message.append_content("No final reply was provided.", complete=True)
    await message.stream_delta()
    return False
