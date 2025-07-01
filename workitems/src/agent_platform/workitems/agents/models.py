from __future__ import annotations

from typing import Literal

from agent_platform.core.payloads.initiate_stream import InitiateStreamPayload

#############################################
# Models that agent-server does not provide
#############################################


class AgentInfo:
    """Basic agent information needed for validation."""

    def __init__(self, agent_id: str, name: str, user_id: str):
        self.agent_id = agent_id
        self.name = name
        self.user_id = user_id


RunStatus = Literal["created", "running", "completed", "failed", "cancelled"]


def status_is_successful(status: RunStatus) -> bool:
    return status in ["completed"]


def status_is_failed(status: RunStatus) -> bool:
    return status in ["failed", "cancelled"]


class InvokeAgentResponse:
    run_id: str
    status: RunStatus

    def __init__(self, run_id: str, status: RunStatus):
        self.run_id = run_id
        self.status = status

    @classmethod
    def model_validate(cls, data: dict) -> InvokeAgentResponse:
        return cls(
            run_id=data["run_id"],
            status=data["status"],
        )


class RunStatusResponse:
    run_id: str
    status: RunStatus

    def __init__(self, run_id: str, status: RunStatus):
        self.run_id = run_id
        self.status = status

    @classmethod
    def model_validate(cls, data: dict) -> RunStatusResponse:
        return cls(
            run_id=data["run_id"],
            status=data["status"],
        )


def dump_initiate_stream_payload(payload: InitiateStreamPayload) -> dict:
    return {
        "agent_id": payload.agent_id,
        "thread_id": payload.thread_id,
        "messages": [message.model_dump() for message in payload.messages],
        # TODO do we need to add tools?
    }
