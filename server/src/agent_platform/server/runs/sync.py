"""Internal synchronous agent invocation."""

import json
from asyncio import FIRST_COMPLETED, create_task, wait
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

import structlog

from agent_platform.core.agent.agent import Agent
from agent_platform.core.context import AgentServerContext
from agent_platform.core.delta.combine_delta import combine_generic_deltas
from agent_platform.core.payloads import InitiateStreamPayload
from agent_platform.core.runs import Run
from agent_platform.core.streaming.delta import (
    StreamingDelta,
    StreamingDeltaAgentFinished,
    StreamingDeltaAgentReady,
    StreamingDeltaMessageBegin,
    StreamingDeltaMessageContent,
)
from agent_platform.core.telemetry.helpers import (
    create_thread_trace_context,
    thread_span_context,
)
from agent_platform.core.thread import Thread
from agent_platform.core.thread.messages import ThreadAgentMessage
from agent_platform.core.user import User
from agent_platform.server.agent_architectures import AgentArchManager
from agent_platform.server.kernel import AgentServerKernel
from agent_platform.server.services import maybe_auto_name_thread
from agent_platform.server.storage import BaseStorage, ThreadNotFoundError

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _ensure_thread_trace_context(
    thread_state: Thread,
    storage: BaseStorage,
) -> None:
    """Ensure thread has trace context, backfilling for legacy threads.

    For threads created before trace context was added at creation time,
    this creates and persists trace context on first run.

    Args:
        thread_state: The thread to check/update. Modified in place.
        storage: Storage for persisting trace context.
    """
    if thread_state.parent_trace_id is not None and thread_state.parent_span_id is not None:
        return

    logger.warning(
        "Backfilling trace context for legacy thread",
        thread_id=thread_state.thread_id,
    )

    trace_id, span_id = create_thread_trace_context(
        thread_name=thread_state.name,
        thread_id=thread_state.thread_id,
        agent_id=thread_state.agent_id,
        user_id=thread_state.user_id,
    )

    # Update thread state in place
    thread_state.parent_trace_id = trace_id
    thread_state.parent_span_id = span_id

    # Persist to database
    await storage.set_thread_trace_context(
        thread_state.user_id,
        thread_state.thread_id,
        parent_trace_id=trace_id,
        parent_span_id=span_id,
    )


async def _upsert_thread_and_messages(
    user: User,
    payload: InitiateStreamPayload,
    storage: BaseStorage,
) -> Thread:
    """
    Fetch or create the user's thread, and persist any incoming messages
    to storage, returning the updated thread state.
    """
    as_thread = InitiateStreamPayload.to_thread(payload, user.user_id)

    try:
        # Try and get the thread from storage (to ensure it exists).
        await storage.get_thread(
            user.user_id,
            as_thread.thread_id,
        )
        # It exists, so persist any new messages to the thread
        for message in payload.messages:
            await storage.add_message_to_thread(
                user.user_id,
                as_thread.thread_id,
                message,
            )
    except ThreadNotFoundError:
        # If the thread didn't exist, upsert it.
        await storage.upsert_thread(
            user.user_id,
            as_thread,
        )

    # Fetch the updated thread state.
    return await storage.get_thread(
        user.user_id,
        as_thread.thread_id,
    )


async def _create_run(
    agent_id: str,
    thread_id: str,
    storage: BaseStorage,
    run_type: Literal["stream", "sync", "async"] = "stream",
) -> Run:
    """Create a new Run record in 'running' state."""
    run = Run(
        run_id=str(uuid4()),
        agent_id=agent_id,
        thread_id=thread_id,
        status="running",
        run_type=run_type,
    )
    await storage.create_run(run)
    return run


async def _update_run_status(
    storage: BaseStorage,
    run: Run | None,
    status: Literal["created", "running", "completed", "failed", "cancelled"],
    finish_reason: str,
    error: str | None = None,
):
    """Mark the run as finished with the given status and optional error info."""
    if run is None:
        return

    run.finished_at = datetime.now(UTC)
    run.status = status
    run.metadata = {
        **run.metadata,
        "finish_reason": finish_reason,
    }
    if error is not None:
        run.metadata["error"] = error

    await storage.upsert_run(run)


async def invoke_agent_sync(
    agent: Agent,
    user: User,
    storage: BaseStorage,
    server_context: AgentServerContext,
    initial_payload: InitiateStreamPayload,
) -> tuple[Thread, list[ThreadAgentMessage]]:
    """Invoke an agent synchronously and return the thread and agent messages.

    This thin wrapper establishes thread trace context, then delegates to _invoke_agent_sync.
    """
    # 1. Upsert thread and messages (before establishing trace context)
    thread_state = await _upsert_thread_and_messages(user, initial_payload, storage)

    # 2. Backfill trace context for legacy threads
    await _ensure_thread_trace_context(thread_state, storage)

    # 3. Establish thread trace context for grouping runs under a common parent
    async with thread_span_context(thread_state=thread_state):
        return await _invoke_agent_sync(
            agent=agent,
            user=user,
            storage=storage,
            server_context=server_context,
            initial_payload=initial_payload,
            thread_state=thread_state,
        )


async def _invoke_agent_sync(
    agent: Agent,
    user: User,
    storage: BaseStorage,
    server_context: AgentServerContext,
    initial_payload: InitiateStreamPayload,
    thread_state: Thread,
) -> tuple[Thread, list[ThreadAgentMessage]]:
    """Invoke an agent synchronously and return the thread and agent messages.
    This is the internal API for running an agent to completion without HTTP dependencies.

    Args:
        agent: The agent to invoke
        user: The user context
        storage: The storage instance
        server_context: The server context for tracing/logging
        initial_payload: The initial payload with thread and messages
        thread_state: The thread state
    Returns:
        Tuple of (Thread, list of ThreadAgentMessages)
    Raises:
        Various exceptions from agent invocation (AgentNotFoundError, etc.)
    """
    agent_arch_manager = AgentArchManager(
        wheels_path="./todo-for-out-of-process/wheels",
        websocket_addr="todo://think-about-out-of-process",
    )

    active_run = None
    collected_events: list[StreamingDelta] = []

    with server_context.start_span("invoke_agent_sync") as span:
        span.set_attribute("langsmith.metadata.agent_id", str(agent.agent_id))
        span.set_attribute("langsmith.metadata.thread_id", str(thread_state.thread_id))
        span.set_attribute(
            "langsmith.metadata.user_id",
            server_context.user_context.user.cr_user_id
            if server_context.user_context.user.cr_user_id
            else server_context.user_context.user.sub,
        )
        span.set_attribute("langsmith.metadata.agent_name", agent.name)
        span.update_name(f"{thread_state.name}")

        # 3. Fetch the agent (already passed in, but log it)
        with server_context.start_span("fetch_agent") as fetch_span:
            fetch_span.set_attribute("agent_id", str(agent.agent_id))
            # Mask sensitive data before logging
            masked_agent_data = Agent.mask_sensitive_data(agent)
            fetch_span.set_attribute("output.value", json.dumps(masked_agent_data))

        # 4. Validate the agent ID from the URL vs. the payload
        if initial_payload.agent_id != agent.agent_id:
            raise ValueError("Agent ID mismatch between agent and payload.")

        # 5. Create a new synchronous run
        with server_context.start_span("create_run") as create_span:
            input_value = {
                "agent_id": agent.agent_id,
                "thread_id": thread_state.thread_id,
                "run_type": "sync",
            }
            create_span.set_attribute("input.value", json.dumps(input_value))
            server_context.increment_counter(
                "sema4ai.agent_server.runs",
                1,
                {
                    "agent_id": agent.agent_id,
                    "thread_id": thread_state.thread_id,
                },
            )
            active_run = await _create_run(agent.agent_id, thread_state.thread_id, storage, run_type="sync")
            create_span.set_attribute("run_id", active_run.run_id)
            create_span.set_attribute("run_type", active_run.run_type)
            create_span.set_attribute("output.value", json.dumps(active_run.model_dump()))
            span.set_attribute("run_id", active_run.run_id)

        # 6. Get the agent runner
        with server_context.start_span("get_agent_runner") as runner_span:
            input_value = {
                "agent_architecture": agent.agent_architecture.name,
                "agent_architecture_version": agent.agent_architecture.version,
                "thread_id": thread_state.thread_id,
            }
            runner_span.set_attribute("input.value", json.dumps(input_value))
            runner = await agent_arch_manager.get_runner(
                agent.agent_architecture.name,
                agent.agent_architecture.version,
                thread_state.thread_id,
            )

        # 7. Start the runner
        with server_context.start_span("start_runner") as start_span:
            input_value = {
                "thread_id": thread_state.thread_id,
                "run_id": active_run.run_id,
            }
            start_span.set_attribute("input.value", json.dumps(input_value))
            await runner.start()

        # 8. Collect the "AgentReady" event
        collected_events.append(
            StreamingDeltaAgentReady(
                run_id=active_run.run_id,
                thread_id=thread_state.thread_id,
                agent_id=agent.agent_id,
                timestamp=datetime.now(UTC),
            ),
        )

        # 9. Schedule the runner's main entry function
        auto_name_task = None

        kernel = AgentServerKernel(server_context, thread_state, agent, active_run)
        if initial_payload.override_model_id:
            kernel.model_selector.override_model(initial_payload.override_model_id)
        auto_name_task = create_task(maybe_auto_name_thread(kernel, storage))
        ca_invoke_task = create_task(runner.invoke(kernel))

        # 10. Task to collect CA events into the list
        async def _collect_ca_events():
            async for event in runner.get_event_stream():
                collected_events.append(event)
                # If the event signals that the CA is finished, stop collecting.
                if isinstance(event, StreamingDeltaAgentFinished):
                    break

        collect_events_task = create_task(_collect_ca_events())

        # 11. Run invoke and collect tasks concurrently
        done, pending = await wait(
            [ca_invoke_task, collect_events_task],
            return_when=FIRST_COMPLETED,
        )

        # Check for errors in completed tasks
        for task in done:
            task_exception = task.exception()
            if task_exception:
                # Propagate the exception to be caught by the caller
                raise task_exception

        # 12. Cancel any leftover tasks and wait for them to finish
        for task in pending:
            task.cancel()
        if pending:
            await wait(pending)  # Wait for cancellation to complete

        # 13. Stop the runner
        await runner.stop()
        if auto_name_task is not None:
            await auto_name_task

        # 14. Mark run as completed
        await _update_run_status(
            storage,
            active_run,
            "completed",
            "normal_completion_sync",
        )

        # 15. Walk through events, every time we see a StreamingDeltaMessageBegin
        # collect every following StreamingDeltaMessageContent until we see
        # a StreamingDeltaMessageEnd. Then we'll combine each "chunk" between
        # a begin and end into a single ThreadAgentMessage and return the list
        # of ThreadAgentMessages.
        message_chunks: list[list] = []
        for event in collected_events:
            if isinstance(event, StreamingDeltaMessageBegin):
                message_chunks.append([])
            elif isinstance(event, StreamingDeltaMessageContent):
                message_chunks[-1].append(event.delta)

        agent_messages = [
            ThreadAgentMessage.model_validate(
                combine_generic_deltas(chunk)
                | {
                    "server_metadata": {
                        # Add some metadata to track which thread ID to reply
                        # to if you want to keep chatting on this thread.
                        "reply_to_thread_id": thread_state.thread_id,
                    },
                }
            )
            for chunk in message_chunks
        ]

        return thread_state, agent_messages
