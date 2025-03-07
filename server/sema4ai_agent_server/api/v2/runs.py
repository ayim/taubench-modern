import traceback
from asyncio import FIRST_COMPLETED, create_task, wait

from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    WebSocketException,
    status,
)
from structlog import get_logger

from agent_server_types_v2.agent import Agent
from agent_server_types_v2.payloads import InitiateStreamPayload
from agent_server_types_v2.thread import Thread
from agent_server_types_v2.user import User
from sema4ai_agent_server.agent_architectures import AgentArchManager
from sema4ai_agent_server.auth.handlers_v2 import AuthedUserWebsocketV2
from sema4ai_agent_server.kernel import AgentServerKernel
from sema4ai_agent_server.storage.v2.errors_v2 import (
    AgentNotFoundError,
    ThreadNotFoundError,
)
from sema4ai_agent_server.storage.v2.option_v2 import get_storage_v2

router = APIRouter()
logger = get_logger(__name__)


async def _get_initial_payload(websocket: WebSocket) -> InitiateStreamPayload:
    initial_data = await websocket.receive_json()
    try:
        return InitiateStreamPayload(**initial_data)
    except (ValueError, TypeError) as e:
        logger.error("Invalid initial payload", error=e)
        raise WebSocketException(
            code=status.WS_1003_UNSUPPORTED_DATA,
            reason="Invalid initial payload",
        ) from e


async def _get_thread_state(user: User, payload: InitiateStreamPayload) -> Thread:
    as_thread = InitiateStreamPayload.to_thread(payload, user.user_id)
    try:
        thread_state = await get_storage_v2().get_thread_v2(
            user.user_id,
            as_thread.thread_id,
        )
        return thread_state
    except ThreadNotFoundError:
        await get_storage_v2().upsert_thread_v2(
            user.user_id,
            as_thread,
        )
        return as_thread


async def _get_agent(user: User, thread_state: Thread) -> Agent:
    try:
        agent = await get_storage_v2().get_agent_v2(
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


# @router.post("/{agent_id}/invoke/sync")
# @router.post("/{agent_id}/invoke/async")


@router.websocket("/{agent_id}/stream")
async def stream_run(  # noqa: C901 (this is a complex entrypoint, may simplify in the future)
    websocket: WebSocket,
    user: AuthedUserWebsocketV2,
    agent_id: str,
):
    agent_arch_manager = AgentArchManager(
        wheels_path="./todo-for-out-of-process/wheels",
        websocket_addr="todo://think-about-out-of-process",
    )

    await websocket.accept()

    try:
        initial_payload = await _get_initial_payload(websocket)
        thread_state = await _get_thread_state(user, initial_payload)
        agent = await _get_agent(user, thread_state)

        # Make sure the initial payload's agent id matches the agent id in the url
        if initial_payload.agent_id != agent_id:
            raise WebSocketException(
                code=status.WS_1008_POLICY_VIOLATION,
                reason="Agent id mismatch",
            )

        # Get our runner instance for the CA
        runner = await agent_arch_manager.get_runner(
            agent.agent_architecture.name,
            agent.agent_architecture.version,
            thread_state.thread_id,
        )

        # Start the CA
        await runner.start()

        # Schedule the CA's main entry function as a background task.
        kernel = AgentServerKernel(user, thread_state, agent)
        ca_invoke_task = create_task(runner.invoke(kernel))

        # This task listens for events from the CA and sends them to the client.
        async def _send_ca_events():
            async for event in runner.get_event_stream():
                # Check if the event signals that the CA is finished.
                # This check could vary based on how your events are defined.
                if isinstance(event, dict) and event.get("type") == "end":
                    await websocket.send_json(event)
                    break  # Exit the loop to trigger shutdown.
                # Send normal events to the client.
                await websocket.send_json({"event": event})

        # This task listens for incoming WebSocket messages
        # and dispatches them to the CA.
        async def _receive_ws_messages():
            while True:
                message = await websocket.receive_json()
                await runner.dispatch_event(message)

        # Create both tasks.
        send_task = create_task(_send_ca_events())
        recv_task = create_task(_receive_ws_messages())

        # Wait until one of the tasks finishes (for example,
        # send_ca_events() detects "end")
        _, pending = await wait(
            [send_task, recv_task, ca_invoke_task],
            return_when=FIRST_COMPLETED,
        )

        # Cancel any pending tasks since we're done.
        for task in pending:
            task.cancel()

        # Wait until all tasks are done.
        await wait(pending)

        # Stop the CA
        await runner.stop()

        # Close the websocket
        await websocket.close()
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except WebSocketException as e:
        logger.error("WebSocket error", error=e)
        await websocket.close(code=e.code, reason=e.reason)
    except Exception as e:
        logger.error(f"Unexpected error in websocket stream for agent {agent_id} : {e}")
        # Log stack trace
        logger.error(traceback.format_exc())
        await websocket.close(
            code=status.WS_1011_INTERNAL_ERROR,
            reason="Unexpected error in websocket stream",
        )
