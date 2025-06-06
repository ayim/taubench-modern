from agent_platform.core.agent.agent import AgentArchitecture
from agent_platform.core.payloads.upsert_agent import UpsertAgentPayload
from agent_platform.server.api.private_v2.compatibility.agent_compat import AgentCompat

DEFAULT_ARCH = AgentArchitecture(name="agent_platform.architectures.default", version="1.0.0")


def _create_payload(metadata: dict) -> UpsertAgentPayload:
    return UpsertAgentPayload(
        name="Test Agent",
        description="desc",
        version="1.0.0",
        runbook="hi",
        agent_architecture=DEFAULT_ARCH,
        metadata=metadata,
    )


class TestWorkerConfigRoundTrip:
    def test_underscore_key(self) -> None:
        payload = _create_payload(
            {
                "mode": "worker",
                "worker_config": {
                    "type": "Document Intelligence",
                    "document_type": "Invoice",
                },
            }
        )
        agent = UpsertAgentPayload.to_agent(payload, user_id="u1")
        assert agent.extra["worker_config"] == {
            "type": "Document Intelligence",
            "document_type": "Invoice",
        }
        compat = AgentCompat.from_agent(agent)
        assert compat.metadata["worker_config"] == {
            "type": "Document Intelligence",
            "document_type": "Invoice",
        }

    def test_dash_key(self) -> None:
        payload = _create_payload(
            {
                "mode": "worker",
                "worker-config": {
                    "type": "Document Intelligence",
                    "document_type": "Invoice",
                },
            }
        )
        agent = UpsertAgentPayload.to_agent(payload, user_id="u1")
        assert agent.extra["worker_config"] == {
            "type": "Document Intelligence",
            "document_type": "Invoice",
        }
        compat = AgentCompat.from_agent(agent)
        assert compat.metadata["worker_config"] == {
            "type": "Document Intelligence",
            "document_type": "Invoice",
        }
