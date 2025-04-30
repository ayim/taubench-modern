import traceback
from asyncio import FIRST_COMPLETED, create_task, wait
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    WebSocketException,
    status,
)
from structlog import get_logger

from agent_platform.core.agent import Agent
from agent_platform.core.context import AgentServerContext
from agent_platform.core.payloads import InitiateStreamPayload
from agent_platform.core.runs import Run
from agent_platform.core.streaming.delta import (
    StreamingDeltaAgentFinished,
    StreamingDeltaAgentReady,
)
from agent_platform.core.thread import Thread
from agent_platform.core.user import User
from agent_platform.server.agent_architectures import AgentArchManager
from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.auth import AuthedUser, AuthedUserWebsocket
from agent_platform.server.kernel import AgentServerKernel
from agent_platform.server.storage import (
    AgentNotFoundError,
    ThreadNotFoundError,
)

router = APIRouter()
logger = get_logger(__name__)


async def _get_initial_payload(websocket: WebSocket) -> InitiateStreamPayload:
    """Receive the initial JSON payload from the client and validate it."""
    initial_data = await websocket.receive_json()
    try:
        return InitiateStreamPayload.model_validate(initial_data)
    except (ValueError, TypeError) as e:
        logger.error("Invalid initial payload", error=e)
        raise WebSocketException(
            code=status.WS_1003_UNSUPPORTED_DATA,
            reason="Invalid initial payload",
        ) from e


async def _upsert_thread_and_messages(
    user: User,
    payload: InitiateStreamPayload,
    storage: StorageDependency,
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
    except ThreadNotFoundError:
        # If the thread didn't exist, upsert it.
        await storage.upsert_thread(
            user.user_id,
            as_thread,
        )

    # Persist any new messages to the thread.
    for message in payload.messages:
        await storage.add_message_to_thread(
            user.user_id,
            as_thread.thread_id,
            message,
        )

    # Fetch the updated thread state.
    return await storage.get_thread(
        user.user_id,
        as_thread.thread_id,
    )


async def _fetch_agent(
    user: User,
    thread_state: Thread,
    storage: StorageDependency,
) -> Agent:
    """Fetch the agent for a given thread, handling any not-found errors."""
    try:
        agent = await storage.get_agent(
            user.user_id,
            str(thread_state.agent_id),
        )
        return agent
    except AgentNotFoundError as e:
        logger.error("Error getting agent", error=e)
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Agent not found",
        ) from e


async def _create_run(agent_id: str, thread_id: str, storage: StorageDependency) -> Run:
    """Create a new Run record in 'running' state."""
    run = Run(
        run_id=str(uuid4()),
        agent_id=agent_id,
        thread_id=thread_id,
        status="running",
        run_type="stream",
    )
    await storage.create_run(run)
    return run


async def _update_run_status(
    storage: StorageDependency,
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


@router.get("/{run_id}/messages")
async def get_run_messages(
    run_id: str,
    user: AuthedUser,
    storage: StorageDependency,
):
    messages = await storage.get_messages_by_parent_run_id(
        user.user_id,
        run_id,
    )
    return messages


@router.websocket("/{agent_id}/stream")
async def stream_run(  # noqa: C901, PLR0915
    websocket: WebSocket,
    user: AuthedUserWebsocket,
    agent_id: str,
    storage: StorageDependency,
):
    """
    WebSocket endpoint to stream a conversation (run) with a given agent.
    """
    agent_arch_manager = AgentArchManager(
        wheels_path="./todo-for-out-of-process/wheels",
        websocket_addr="todo://think-about-out-of-process",
    )

    await websocket.accept()

    active_run: Run | None = None

    try:
        # Create agent server context
        server_context = AgentServerContext.from_request(
            request=websocket,
            user=user,
            version="2.0.0",  # TODO: versionbump enable this. Pull from constant.
        )

        # 1. Receive and validate initial payload
        initial_payload = await _get_initial_payload(websocket)

        # Start a new trace for this stream
        with server_context.start_span("stream_run") as span:
            # Add string attributes that are safe for OTEL
            span.set_attribute("agent_id", str(agent_id))
            span.set_attribute("thread_id", str(initial_payload.thread_id))
            span.set_attribute("user_id", server_context.user_context.user.user_id)

            # 2. Upsert thread and messages
            with server_context.start_span("upsert_thread_and_messages") as upsert_span:
                upsert_span.set_attribute("thread_id", str(initial_payload.thread_id))
                thread_state = await _upsert_thread_and_messages(
                    user,
                    initial_payload,
                    storage,
                )
                upsert_span.set_attribute(
                    "message_count", len(initial_payload.messages)
                )

            # 3. Fetch the agent
            with server_context.start_span("fetch_agent") as fetch_span:
                fetch_span.set_attribute("agent_id", str(agent_id))
                agent = await _fetch_agent(user, thread_state, storage)
                fetch_span.set_attribute("agent_name", agent.name)

            # 4. Validate the agent ID from the URL vs. the payload
            if initial_payload.agent_id != agent_id:
                raise WebSocketException(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="Agent id mismatch",
                )

            # 5. Create a new streaming run
            with server_context.start_span("create_run") as create_span:
                active_run = await _create_run(
                    agent_id, thread_state.thread_id, storage
                )
                create_span.set_attribute("run_id", active_run.run_id)
                create_span.set_attribute("run_type", active_run.run_type)
                span.set_attribute("run_id", active_run.run_id)

            # 6. Get the agent runner
            with server_context.start_span("get_agent_runner") as runner_span:
                runner_span.set_attribute(
                    "agent_architecture", agent.agent_architecture.name
                )
                runner_span.set_attribute(
                    "agent_version", agent.agent_architecture.version
                )
                runner = await agent_arch_manager.get_runner(
                    agent.agent_architecture.name,
                    agent.agent_architecture.version,
                    thread_state.thread_id,
                )

            # 7. Start the runner
            with server_context.start_span("start_runner"):
                await runner.start()

            # 8. Notify the client we are ready
            await websocket.send_json(
                StreamingDeltaAgentReady(
                    run_id=active_run.run_id,
                    thread_id=thread_state.thread_id,
                    agent_id=agent_id,
                    timestamp=datetime.now(UTC),
                ).model_dump(),
            )

            # 9. Schedule the runner's main entry function
            kernel = AgentServerKernel(server_context, thread_state, agent, active_run)
            ca_invoke_task = create_task(runner.invoke(kernel))

            # 10. Task to forward CA events to client
            async def _send_ca_events():
                async for event in runner.get_event_stream():
                    # If the event signals that the CA is finished, break.
                    if isinstance(event, StreamingDeltaAgentFinished):
                        await websocket.send_json(event.model_dump())
                        break
                    # Otherwise, forward the event.
                    await websocket.send_json(event.model_dump())

            # 11. Task to receive client messages and dispatch to the runner
            async def _receive_ws_messages():
                while True:
                    message = await websocket.receive_json()
                    await runner.dispatch_event(message)

            # 12. Run both tasks concurrently
            send_task = create_task(_send_ca_events())
            recv_task = create_task(_receive_ws_messages())

            done, pending = await wait(
                [send_task, recv_task, ca_invoke_task],
                return_when=FIRST_COMPLETED,
            )

            # 13. Cancel any leftover tasks and wait
            for task in pending:
                task.cancel()
            await wait(pending)

            # 14. Stop the runner
            await runner.stop()

            # 15. If everything finished without error, mark run as succeeded
            #     (Assuming if the code reaches here, we consider it "succeeded".)
            await _update_run_status(
                storage,
                active_run,
                "completed",
                "normal_completion",
            )

            # 16. Close the WebSocket
            await websocket.close()

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
        # If user disconnects, mark run as "cancelled"
        await _update_run_status(
            storage,
            active_run,
            "cancelled",
            "websocket_disconnected",
        )

    except WebSocketException as e:
        logger.error("WebSocket error", error=e)
        await websocket.close(code=e.code, reason=e.reason)
        # Update the run status to failed
        await _update_run_status(
            storage,
            active_run,
            "failed",
            "websocket_error",
            error=str(e),
        )

    except Exception as e:
        logger.error(
            f"Unexpected error in websocket stream for agent {agent_id}: {e}",
        )
        logger.error(traceback.format_exc())
        await websocket.close(
            code=status.WS_1011_INTERNAL_ERROR,
            reason="Unexpected error in websocket stream",
        )
        # Update the run status to failed
        await _update_run_status(
            storage,
            active_run,
            "failed",
            "unexpected_error",
            error=str(e),
        )
