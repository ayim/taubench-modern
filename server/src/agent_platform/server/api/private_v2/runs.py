import json
import traceback
from asyncio import (
    FIRST_COMPLETED,
    CancelledError,
    create_task,
    ensure_future,
    gather,
    wait,
    wait_for,
)
from datetime import UTC, datetime
from json import JSONDecodeError
from typing import Literal
from uuid import uuid4

import structlog
from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
    WebSocketException,
    status,
)
from fastapi.websockets import WebSocketState

from agent_platform.core.agent.agent import Agent
from agent_platform.core.context import AgentServerContext
from agent_platform.core.delta.base import GenericDelta
from agent_platform.core.delta.combine_delta import combine_generic_deltas
from agent_platform.core.payloads import InitiateStreamPayload
from agent_platform.core.payloads.ephemeral_stream import EphemeralStreamPayload
from agent_platform.core.payloads.upsert_agent import UpsertAgentPayload
from agent_platform.core.runs import Run
from agent_platform.core.streaming.delta import (
    StreamingDelta,
    StreamingDeltaAgentFinished,
    StreamingDeltaAgentReady,
    StreamingDeltaMessageBegin,
    StreamingDeltaMessageContent,
)
from agent_platform.core.thread import Thread
from agent_platform.core.thread.content import ThreadTextContent
from agent_platform.core.thread.messages import ThreadAgentMessage
from agent_platform.core.user import User
from agent_platform.server.agent_architectures import AgentArchManager
from agent_platform.server.api.dependencies import StorageDependency
from agent_platform.server.auth import AuthedUser, AuthedUserWebsocket
from agent_platform.server.kernel import AgentServerKernel
from agent_platform.server.storage import (
    AgentNotFoundError,
    RunNotFoundError,
    ThreadNotFoundError,
)

router = APIRouter()
logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def _get_initial_payload(
    websocket: WebSocket,
    timeout: float = 10.0,
) -> InitiateStreamPayload:
    """Receive the initial JSON payload from the client and validate it."""
    try:
        initial_data = await wait_for(websocket.receive_json(), timeout)
    except TimeoutError as e:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Initial payload not received in time",
        ) from e
    except JSONDecodeError as e:
        raise WebSocketException(
            code=status.WS_1003_UNSUPPORTED_DATA,
            reason="Invalid initial payload: failed to parse JSON",
        ) from e

    try:
        return InitiateStreamPayload.model_validate(initial_data)
    except (ValueError, TypeError, KeyError, AttributeError) as e:
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


@router.get("/{run_id}/status")
async def get_run_status(
    run_id: str,
    user: AuthedUser,
    storage: StorageDependency,
):
    """
    Get the status of a run by its ID.
    Returns the run's current status.
    """
    try:
        run = await storage.get_run(run_id)
        return {
            "run_id": run.run_id,
            "status": run.status,
        }
    except Exception as e:
        # If run not found or any other error, return 404

        if isinstance(e, RunNotFoundError):
            raise e
        raise HTTPException(status_code=404, detail="Run not found") from None


@router.websocket("/ephemeral/stream")
async def ephemeral_stream_run(  # noqa: C901, PLR0915
    websocket: WebSocket,
    user: AuthedUserWebsocket,
    storage: StorageDependency,
):
    """WebSocket endpoint for ephemeral agent runs."""

    async def _safe_close_websocket(
        websocket: WebSocket,
        *,
        code: int = status.WS_1000_NORMAL_CLOSURE,
        reason: str | None = None,
    ) -> None:
        if WebSocketState.DISCONNECTED in {
            websocket.application_state,
            websocket.client_state,
        }:
            return
        try:
            await websocket.close(code=code, reason=reason)
        except RuntimeError:
            pass
        except Exception:
            pass

    agent_arch_manager = AgentArchManager(
        wheels_path="./todo-for-out-of-process/wheels",
        websocket_addr="todo://think-about-out-of-process",
    )

    await websocket.accept()

    agent: Agent | None = None
    try:
        initial_data = await websocket.receive_json()
        try:
            payload = EphemeralStreamPayload.model_validate(initial_data)
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            logger.error("Invalid ephemeral payload", error=e)
            raise WebSocketException(
                code=status.WS_1003_UNSUPPORTED_DATA,
                reason="Invalid ephemeral payload",
            ) from e

        agent = UpsertAgentPayload.to_agent(payload.agent, user_id=user.user_id)
        await storage.upsert_agent(user.user_id, agent)

        # Create thread without using InitiateStreamPayload constructor
        # since we're in an ephemeral context
        thread = Thread(
            user_id=user.user_id,
            agent_id=agent.agent_id,
            name=payload.name or "Ephemeral Thread",
            thread_id=str(uuid4()),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            messages=payload.messages,
            metadata=payload.metadata,
        )
        await storage.upsert_thread(user.user_id, thread)

        run = Run(
            run_id=str(uuid4()),
            agent_id=agent.agent_id,
            thread_id=thread.thread_id,
            status="running",
            run_type="stream",
        )
        await storage.upsert_run(run)

        server_context = AgentServerContext.from_request(
            request=websocket,
            user=user,
            version="2.0.0",
        )

        runner = await agent_arch_manager.get_runner(
            agent.agent_architecture.name,
            agent.agent_architecture.version,
            thread.thread_id,
        )

        await runner.start()

        await websocket.send_json(
            StreamingDeltaAgentReady(
                run_id=run.run_id,
                thread_id=thread.thread_id,
                agent_id=agent.agent_id,
                timestamp=datetime.now(UTC),
            ).model_dump(),
        )

        kernel = AgentServerKernel(
            server_context,
            thread,
            agent,
            run,
            client_tools=[tool.to_tool_definition() for tool in payload.client_tools],
        )
        ca_invoke_task = create_task(runner.invoke(kernel))

        async def _send_events():
            try:
                async for event in runner.get_event_stream():
                    try:
                        await websocket.send_json(event.model_dump())
                        if isinstance(event, StreamingDeltaAgentFinished):
                            break
                    except (WebSocketDisconnect, RuntimeError):
                        pass
            except CancelledError:
                logger.info(
                    "CA event sending task cancelled, likely client disconnected",
                )

        async def _receive_ws_messages():
            try:
                while True:
                    message = await websocket.receive_json()
                    await runner.dispatch_event(message)
            except CancelledError:
                logger.info(
                    "Client message receiving task cancelled, likely client disconnected",
                )

        _send_task = create_task(_send_events())
        recv_task = create_task(_receive_ws_messages())

        done, pending = await wait(
            {recv_task, ca_invoke_task, _send_task},
            return_when=FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()

        await gather(*pending, return_exceptions=True)
        await runner.stop()
        await _safe_close_websocket(websocket)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
        await _safe_close_websocket(websocket)
    except WebSocketException as e:
        logger.error("WebSocket error in ephemeral stream", error=e)
        await _safe_close_websocket(websocket, code=e.code, reason=e.reason)
    except Exception as e:
        logger.error(f"Unexpected error in ephemeral stream: {e}")
        logger.error(traceback.format_exc())
        await _safe_close_websocket(
            websocket,
            code=status.WS_1011_INTERNAL_ERROR,
            reason="Unexpected error in websocket stream",
        )
    finally:
        # Try and delete, we may not have even got to create; this should cascade
        # to delete the thread and run (and any scoped storage)
        try:
            if agent:
                await storage.delete_agent(user.user_id, agent.agent_id)
        except Exception:
            pass


@router.websocket("/{agent_id}/stream")
async def stream_run(  # noqa: C901, PLR0912, PLR0915
    websocket: WebSocket,
    user: AuthedUserWebsocket,
    agent_id: str,
    storage: StorageDependency,
):
    """
    WebSocket endpoint to stream a conversation (run) with a given agent.
    """

    async def _safe_close_websocket(
        websocket: WebSocket,
        *,
        code: int = status.WS_1000_NORMAL_CLOSURE,
        reason: str | None = None,
    ) -> None:
        # If *either* side of the connection is already marked "disconnected"
        # there's no point sending another close frame.
        if WebSocketState.DISCONNECTED in {
            websocket.application_state,
            websocket.client_state,
        }:
            return

        try:
            await websocket.close(code=code, reason=reason)
        except RuntimeError:
            # Another coroutine won the race and closed it first.
            pass
        except Exception:
            # Don't let a late close explode the main handler.
            pass

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
            agent_id=agent_id,
        )

        attributes = {
            "agent_id": agent.agent_id,
        }
        if initial_payload.thread_id is not None:
            attributes["thread_id"] = initial_payload.thread_id

        server_context.increment_counter(
            "sema4ai.agent_server.messages", len(initial_payload.messages), attributes
        )

        # Start a new trace for this stream
        with server_context.start_span(
            "stream_run",
        ) as span:
            # Add string attributes that are safe for OTEL
            span.set_attribute("langsmith.metadata.agent_id", str(agent_id))
            span.set_attribute("langsmith.metadata.thread_id", str(initial_payload.thread_id))
            span.set_attribute(
                "langsmith.metadata.user_id",
                server_context.user_context.user.cr_user_id
                if server_context.user_context.user.cr_user_id
                else server_context.user_context.user.sub,
            )
            span.set_attribute("langsmith.metadata.agent_name", agent.name)

            # 2. Upsert thread and messages
            with server_context.start_span("upsert_thread_and_messages") as upsert_span:
                input_value = {
                    "thread_id": str(initial_payload.thread_id),
                    "message_count": len(initial_payload.messages),
                }
                upsert_span.set_attribute("input.value", json.dumps(input_value))
                thread_state = await _upsert_thread_and_messages(
                    user,
                    initial_payload,
                    storage,
                )
                formatted_thread_state = thread_state.model_dump()
                formatted_thread_state.pop("messages")
                upsert_span.set_attribute("output.value", json.dumps(formatted_thread_state))
            span.update_name(f"{thread_state.name}")
            try:
                last_user_message = thread_state.messages[-1]
                formatted_message = {
                    "role": "user",
                    "content": (
                        last_user_message.content[0].text
                        if isinstance(last_user_message.content[0], ThreadTextContent)
                        else str(last_user_message.content[0])
                    ),
                }
                span.set_attribute(
                    "input.value",
                    json.dumps(formatted_message),
                )
            except Exception as e:
                logger.error(f"Could not prepare inputs for parent span: {e}")
            # 3. Fetch the agent
            with server_context.start_span("fetch_agent") as fetch_span:
                fetch_span.set_attribute("agent_id", str(agent_id))
                # Mask sensitive data before logging
                masked_agent_data = Agent.mask_sensitive_data(agent)
                fetch_span.set_attribute("output.value", json.dumps(masked_agent_data))

            # 4. Validate the agent ID from the URL vs. the payload
            if initial_payload.agent_id != agent_id:
                raise WebSocketException(
                    code=status.WS_1008_POLICY_VIOLATION,
                    reason="Agent ID mismatch in URL and payload.",
                )

            # 5. Create a new streaming run
            with server_context.start_span("create_run") as create_span:
                attributes = {
                    "agent_id": agent.agent_id,
                    "thread_id": thread_state.thread_id,
                }

                server_context.increment_counter("sema4ai.agent_server.runs", 1, attributes)
                active_run = await _create_run(
                    agent_id, thread_state.thread_id, storage, run_type="stream"
                )
                create_span.set_attribute("run_id", active_run.run_id)
                create_span.set_attribute("run_type", active_run.run_type)
                span.set_attribute("run_id", active_run.run_id)
                create_span.set_attribute("output.value", json.dumps(active_run.model_dump()))

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
            kernel = AgentServerKernel(
                server_context,
                thread_state,
                agent,
                active_run,
                # Include any client-provided tools in the kernel
                client_tools=[tool.to_tool_definition() for tool in initial_payload.client_tools],
            )
            ca_invoke_task = create_task(runner.invoke(kernel))

            # 10. Task to forward CA events to client
            event_array = []

            async def _send_ca_events():
                try:
                    async for event in runner.get_event_stream():
                        try:
                            # Forward the event.
                            event_array.append(event.model_dump())
                            await websocket.send_json(event.model_dump())
                            # If the event signals that the CA is finished, break.
                            if isinstance(event, StreamingDeltaAgentFinished):
                                break
                        except (WebSocketDisconnect, RuntimeError):
                            # Socket is already gone - swallow the error
                            pass
                except CancelledError:
                    logger.info(
                        "CA event sending task cancelled, likely client disconnected",
                    )
                finally:
                    span.set_attribute("output.value", str(event_array))

            # 11. Task to receive client messages and dispatch to the runner
            async def _receive_ws_messages():
                try:
                    while True:
                        message = await websocket.receive_json()
                        await runner.dispatch_event(message)
                except CancelledError:
                    logger.info(
                        "Client message receiving task cancelled, likely client disconnected",
                    )

            send_task = create_task(_send_ca_events())
            recv_task = create_task(_receive_ws_messages())

            # Group agent's core invocation and its event sending
            agent_processing_task = ensure_future(gather(ca_invoke_task, send_task))

            # All top-level tasks managed by stream_run
            all_managed_tasks = {
                ca_invoke_task,
                send_task,
                recv_task,
            }

            exception_to_propagate = None
            try:
                # Wait for *either* client message handling (recv_task)
                # or agent processing (agent_processing_and_sending_task) to complete
                done_first, pending_after_first = await wait(
                    {recv_task, agent_processing_task},
                    return_when=FIRST_COMPLETED,
                )

                for task in done_first:
                    if exc := task.exception():
                        exception_to_propagate = exc
                        break  # Found primary error

                if not exception_to_propagate:
                    # No error in first-completed tasks. This means normal completion
                    # e.g., agent_processing_and_sending_task finished successfully
                    # The tasks in pending_after_first still need explicit cancellation
                    for pending_task_group in pending_after_first:
                        # pending_task_group is either recv_task or
                        # agent_processing_and_sending_task
                        if pending_task_group is recv_task and not recv_task.done():
                            recv_task.cancel()
                        elif pending_task_group is agent_processing_task:
                            agent_processing_task.cancel()

                    # If we are here, stream_run considers this a normal completion path
                    await _update_run_status(storage, active_run, "completed", "normal_completion")
                    await _safe_close_websocket(websocket)

            except Exception as e:
                exception_to_propagate = e

            finally:
                # This block ensures cleanup regardless of how the try block was exited.
                # Cancel any tasks from our main set that aren't done.
                for task_to_clean in all_managed_tasks:
                    if not task_to_clean.done():
                        task_to_clean.cancel()

                # Await all of them to settle (collecting any
                # CancelledErrors or other exceptions)
                await gather(*all_managed_tasks, return_exceptions=True)
                await runner.stop()

            if exception_to_propagate:
                raise exception_to_propagate

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
        # If user disconnects, mark run as "cancelled"
        await _update_run_status(
            storage,
            active_run,
            "cancelled",
            "websocket_disconnected",
        )

    except AgentNotFoundError as e:
        logger.error("Error getting agent", error=e)
        await _update_run_status(storage, active_run, "failed", "agent_not_found", error=str(e))
        # Re-raise as WebSocketException as per original logic, or handle directly
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason="Agent not found",
        ) from e

    except WebSocketException as e:
        logger.error("WebSocket error", error=e)
        await _safe_close_websocket(websocket, code=e.code, reason=e.reason)
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
        await _safe_close_websocket(
            websocket,
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
            agent_id=agent_id,
        )

        # 1. Initial payload is already validated by FastAPI
        # as a request body parameter
        with server_context.start_span(
            "sync_run",
        ) as span:
            span.set_attribute("langsmith.metadata.agent_id", str(agent_id))
            span.set_attribute("langsmith.metadata.thread_id", str(initial_payload.thread_id))
            span.set_attribute(
                "langsmith.metadata.user_id",
                server_context.user_context.user.cr_user_id
                if server_context.user_context.user.cr_user_id
                else server_context.user_context.user.sub,
            )
            span.set_attribute("langsmith.metadata.agent_name", agent.name)

            # 2. Upsert thread and messages
            with server_context.start_span("upsert_thread_and_messages") as upsert_span:
                input_value = {
                    "thread_id": str(initial_payload.thread_id),
                    "message_count": len(initial_payload.messages),
                }
                upsert_span.set_attribute("input.value", json.dumps(input_value))
                thread_state = await _upsert_thread_and_messages(
                    user,
                    initial_payload,
                    storage,
                )
                output = thread_state.model_dump()
                output.pop("messages", None)
                upsert_span.set_attribute("output.value", json.dumps(output))
            span.update_name(f"{thread_state.name}")

            # 3. Fetch the agent
            with server_context.start_span("fetch_agent") as fetch_span:
                fetch_span.set_attribute("agent_id", str(agent_id))
                # Mask sensitive data before logging
                masked_agent_data = Agent.mask_sensitive_data(agent)
                fetch_span.set_attribute("output.value", json.dumps(masked_agent_data))

            # 4. Validate the agent ID from the URL vs. the payload
            if initial_payload.agent_id != agent_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Agent ID mismatch in URL and payload.",
                )

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
                active_run = await _create_run(
                    agent_id, thread_state.thread_id, storage, run_type="sync"
                )
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


@router.post("/{agent_id}/async")
async def async_run(  # noqa: C901, PLR0915
    agent_id: str,
    initial_payload: InitiateStreamPayload,
    user: AuthedUser,
    storage: StorageDependency,
    request: Request,
):
    """
    Asynchronous endpoint to start a run with a given agent and return an acknowledgment.
    The client doesn't need to wait for the run to complete.
    """
    agent_arch_manager = AgentArchManager(
        wheels_path="./todo-for-out-of-process/wheels",
        websocket_addr="todo://think-about-out-of-process",
    )

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
            version="2.0.0",
            observability_config=observability_config,
            agent_id=agent_id,
        )

        # Start a new trace for this async run
        with server_context.start_span(
            "async_run",
        ) as span:
            # Add string attributes that are safe for OTEL
            span.set_attribute("langsmith.metadata.agent_id", str(agent_id))
            span.set_attribute("langsmith.metadata.thread_id", str(initial_payload.thread_id))
            span.set_attribute(
                "langsmith.metadata.user_id",
                server_context.user_context.user.cr_user_id
                if server_context.user_context.user.cr_user_id
                else server_context.user_context.user.sub,
            )
            span.set_attribute("langsmith.metadata.agent_name", agent.name)

            # 1. Validate the agent ID from the URL vs. the payload
            if initial_payload.agent_id != agent_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Agent ID mismatch in URL and payload.",
                )

            # 2. Upsert thread and messages
            with server_context.start_span("upsert_thread_and_messages") as upsert_span:
                input_value = {
                    "thread_id": str(initial_payload.thread_id),
                    "message_count": len(initial_payload.messages),
                }
                upsert_span.set_attribute("input.value", json.dumps(input_value))
                thread_state = await _upsert_thread_and_messages(
                    user,
                    initial_payload,
                    storage,
                )
                upsert_span.set_attribute("output.value", json.dumps(thread_state.model_dump()))
            span.update_name(f"{thread_state.name}")

            # 3. Create a new asynchronous run
            with server_context.start_span("create_run") as create_span:
                input_value = {
                    "agent_id": agent.agent_id,
                    "thread_id": thread_state.thread_id,
                    "run_type": "async",
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
                active_run = await _create_run(
                    agent_id, thread_state.thread_id, storage, run_type="async"
                )
                create_span.set_attribute("run_id", active_run.run_id)
                create_span.set_attribute("run_type", active_run.run_type)
                create_span.set_attribute("output.value", json.dumps(active_run.model_dump()))
                span.set_attribute("run_id", active_run.run_id)

            # 4. Start the background task to run the agent
            async def _background_agent_run():
                """Background task to execute the agent run."""
                try:
                    # Get the agent runner
                    runner = await agent_arch_manager.get_runner(
                        agent.agent_architecture.name,
                        agent.agent_architecture.version,
                        thread_state.thread_id,
                    )

                    # Start the runner
                    await runner.start()

                    # Create kernel and invoke the agent
                    kernel = AgentServerKernel(server_context, thread_state, agent, active_run)
                    await runner.invoke(kernel)

                    # Stop the runner
                    await runner.stop()

                    # Mark run as completed
                    await _update_run_status(
                        storage,
                        active_run,
                        "completed",
                        "normal_completion_async",
                    )

                except Exception as e:
                    logger.error(
                        f"Error in background async run for agent {agent_id}: {e}",
                    )
                    logger.error(traceback.format_exc())
                    await _update_run_status(
                        storage,
                        active_run,
                        "failed",
                        "background_error_async",
                        error=str(e),
                    )

            # Start the background task
            background_task = create_task(_background_agent_run())

            # Don't await the background task - let it run independently
            # Add a callback to handle any exceptions that might occur
            def _handle_background_task_done(task):
                if task.exception():
                    logger.error(
                        f"Background task for run {active_run.run_id} failed: {task.exception()}"
                    )

            background_task.add_done_callback(_handle_background_task_done)

            # 5. Return acknowledgment immediately
            return {
                "run_id": active_run.run_id,
                "status": "running",
            }

    except AgentNotFoundError as e:
        logger.error("Error getting agent", error=e)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        ) from e

    except HTTPException as e:
        # Log and re-raise HTTPExceptions
        logger.error(
            f"HTTPException in async run for agent {agent_id}: {e.detail}",
            exc_info=e,
        )
        raise e

    except Exception as e:
        logger.error(
            f"Unexpected error in async run for agent {agent_id}: {e}",
        )
        logger.error(traceback.format_exc())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during the asynchronous run.",
        ) from e
