import traceback
from asyncio import FIRST_COMPLETED, create_task, wait
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
    WebSocketException,
    status,
)
from structlog import get_logger

from agent_platform.core.context import AgentServerContext
from agent_platform.core.delta.base import GenericDelta
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
from agent_platform.core.thread import Thread
from agent_platform.core.thread.messages import ThreadAgentMessage
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
    storage: StorageDependency,
    run_type: Literal["stream", "sync"] = "stream",
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
    server_context = None

    try:
        # 1. Receive and validate initial payload
        initial_payload = await _get_initial_payload(websocket)

        agent = await storage.get_agent(user.user_id, agent_id)

        # Fetch the first LangSmith observability config
        observability_config = None
        for config in agent.observability_configs:
            if config.type == "langsmith":
                observability_config = config
                break

        if observability_config is None:
            logger.info("No LangSmith observability config found, using default")

        # Create agent server context
        server_context = AgentServerContext.from_request(
            request=websocket,
            user=user,
            version="2.0.0",
            observability_config=observability_config,
        )

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
                # We already fetched the agent above, so just add attributes
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
                    agent_id, thread_state.thread_id, storage, run_type="stream"
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

    except AgentNotFoundError as e:
        logger.error("Error getting agent", error=e)
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Agent not found",
        ) from e

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


@router.post("/{agent_id}/sync", response_model=list[ThreadAgentMessage])
async def sync_run(  # noqa: C901, PLR0912, PLR0915
    agent_id: str,
    initial_payload: InitiateStreamPayload,
    user: AuthedUser,
    storage: StorageDependency,
    request: Request,
):
    """
    Synchronous endpoint to run a conversation with a given agent and return all events.
    """
    agent_arch_manager = AgentArchManager(
        wheels_path="./todo-for-out-of-process/wheels",
        websocket_addr="todo://think-about-out-of-process",
    )

    active_run: Run | None = None
    collected_events: list[StreamingDelta] = []

    try:
        agent = await storage.get_agent(user.user_id, agent_id)

        # Fetch the first LangSmith observability config
        observability_config = None
        for config in agent.observability_configs:
            if config.type == "langsmith":
                observability_config = config
                break

        if observability_config is None:
            logger.info("No LangSmith observability config found, using default")

        # Create agent server context for HTTP request
        server_context = AgentServerContext.from_request(
            request=request,
            user=user,
            version="2.0.0",  # TODO: versionbump enable this. Pull from constant.
            observability_config=observability_config,
        )

        # 1. Initial payload is already validated by FastAPI
        # as a request body parameter
        with server_context.start_span("sync_run") as span:
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
                # We already fetched the agent above, so just add attributes
                fetch_span.set_attribute("agent_name", agent.name)

            # 4. Validate the agent ID from the URL vs. the payload
            if initial_payload.agent_id != agent_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Agent ID mismatch in URL and payload.",
                )

            # 5. Create a new synchronous run
            with server_context.start_span("create_run") as create_span:
                active_run = await _create_run(
                    agent_id, thread_state.thread_id, storage, run_type="sync"
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

            # 8. Collect the "AgentReady" event (instead of sending)
            # This is where you start assembling events.
            collected_events.append(
                StreamingDeltaAgentReady(
                    run_id=active_run.run_id,
                    thread_id=thread_state.thread_id,
                    agent_id=agent_id,
                    timestamp=datetime.now(UTC),
                ),
            )

            # 9. Schedule the runner's main entry function
            kernel = AgentServerKernel(server_context, thread_state, agent, active_run)
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
            # No client message receiving task for a sync endpoint.
            done, pending = await wait(
                [ca_invoke_task, collect_events_task],
                return_when=FIRST_COMPLETED,
            )

            # Check for errors in completed tasks
            for task in done:
                task_exception = task.exception()
                if task_exception:
                    # Propagate the exception to be caught by the main try-except block
                    raise task_exception

            # 12. Cancel any leftover tasks and wait for them to finish
            for task in pending:
                task.cancel()
            if pending:
                await wait(pending)  # Wait for cancellation to complete

            # 13. Stop the runner
            await runner.stop()

            # 14. If everything finished without error, mark run as completed
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
            message_chunks: list[list[GenericDelta]] = []
            for event in collected_events:
                if isinstance(event, StreamingDeltaMessageBegin):
                    message_chunks.append([])
                elif isinstance(event, StreamingDeltaMessageContent):
                    message_chunks[-1].append(event.delta)

            return [
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

    except AgentNotFoundError as e:
        logger.error("Error getting agent", error=e)
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Agent not found",
        ) from e

    except HTTPException as e:
        # Log and re-raise HTTPExceptions
        logger.error(
            f"HTTPException in sync run for agent {agent_id}: {e.detail}",
            exc_info=e,
        )
        await _update_run_status(
            storage,
            active_run,
            "failed",
            "http_error",
            error=str(e.detail),
        )
        raise e

    except Exception as e:
        logger.error(
            f"Unexpected error in sync run for agent {agent_id}: {e}",
        )
        logger.error(traceback.format_exc())
        await _update_run_status(
            storage,
            active_run,
            "failed",
            "unexpected_error_sync",
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during the synchronous run.",
        ) from e
