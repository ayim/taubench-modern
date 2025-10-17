from types import SimpleNamespace

from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.content.text import ThreadTextContent
from agent_platform.core.thread.thread import Thread
from agent_platform.server.api.private_v2.evals import (
    ActionCalling,
    CreateScenarioPayload,
    FlowAdherence,
    ResponseAccuracy,
)
from agent_platform.server.evals.run_scenario import (
    ScenarioEvaluationPreferences,
    _resolve_scenario_evaluation_preferences,
)


def _make_thread(thread_id: str = "thread-1") -> Thread:
    user_message = ThreadMessage(
        content=[ThreadTextContent(text="User says hi")],
        role="user",
        complete=True,
    )
    agent_message = ThreadMessage(
        content=[ThreadTextContent(text="Agent responds")],
        role="agent",
        complete=True,
    )
    return Thread(
        user_id="user-1",
        agent_id="agent-1",
        name="demo-thread",
        thread_id=thread_id,
        messages=[agent_message, user_message],
    )


def _make_scenario_stub(
    *, metadata: dict | None = None, description: str = "Default description"
) -> SimpleNamespace:
    return SimpleNamespace(
        description=description,
        metadata=metadata or {},
    )


def test_create_scenario_payload_adds_evaluation_metadata() -> None:
    payload = CreateScenarioPayload(
        name="My Scenario",
        description="Baseline description",
        thread_id="thread-1",
        evaluation_criteria=[
            ActionCalling(),
            FlowAdherence(),
            ResponseAccuracy("  Agent should confirm order details.  "),
        ],
    )
    thread = _make_thread("thread-1")

    scenario = CreateScenarioPayload.to_scenario(payload, user_id="user-1", thread=thread)

    assert scenario.metadata == {
        "evaluations": {
            "action_calling": {"enabled": True},
            "flow_adherence": {"enabled": True},
            "response_accuracy": {
                "enabled": True,
                "expectation": "Agent should confirm order details.",
            },
        }
    }


def test_create_scenario_payload_includes_action_calling_policy() -> None:
    payload = CreateScenarioPayload(
        name="Policy Scenario",
        description="Desc",
        thread_id="thread-1",
        evaluation_criteria=[
            ActionCalling(
                assert_all_consumed=True,
                allow_llm_arg_validation=False,
                allow_llm_interpolation=True,
            )
        ],
    )
    thread = _make_thread("thread-1")

    scenario = CreateScenarioPayload.to_scenario(payload, user_id="user-1", thread=thread)

    assert scenario.metadata["evaluations"] == {
        "action_calling": {
            "enabled": True,
            "assert_all_consumed": True,
            "allow_llm_arg_validation": False,
            "allow_llm_interpolation": True,
        }
    }
    assert scenario.metadata["drift_policy"] == {
        "assert_all_consumed": True,
        "allow_llm_arg_validation": False,
        "allow_llm_interpolation": True,
    }


def test_create_scenario_payload_keeps_metadata_empty_when_not_configured() -> None:
    payload = CreateScenarioPayload(
        name="Legacy Scenario",
        description="Legacy description",
        thread_id="thread-1",
    )
    thread = _make_thread("thread-1")

    scenario = CreateScenarioPayload.to_scenario(payload, user_id="user-1", thread=thread)

    assert "evaluations" not in scenario.metadata


def test_resolve_preferences_defaults_when_metadata_missing() -> None:
    scenario = _make_scenario_stub(metadata={})

    preferences = _resolve_scenario_evaluation_preferences(scenario)  # type: ignore

    assert preferences == ScenarioEvaluationPreferences(
        action_calling=True,
        flow_adherence=True,
        response_accuracy=True,
        response_accuracy_expectation=scenario.description,
    )


def test_resolve_preferences_honours_metadata_selection() -> None:
    metadata = {
        "evaluations": {
            "action_calling": {"enabled": False},
            "flow_adherence": {"enabled": True},
            "response_accuracy": {
                "enabled": True,
                "expectation": "Follow the escalation policy.",
            },
        }
    }
    scenario = _make_scenario_stub(metadata=metadata, description="Original description")

    preferences = _resolve_scenario_evaluation_preferences(scenario)  # type: ignore

    assert preferences == ScenarioEvaluationPreferences(
        action_calling=False,
        flow_adherence=True,
        response_accuracy=True,
        response_accuracy_expectation="Follow the escalation policy.",
    )


def test_resolve_preferences_uses_explicit_empty_configuration() -> None:
    scenario = _make_scenario_stub(metadata={"evaluations": {}}, description="No checks")

    preferences = _resolve_scenario_evaluation_preferences(scenario)  # type: ignore

    assert preferences == ScenarioEvaluationPreferences(
        action_calling=False,
        flow_adherence=False,
        response_accuracy=False,
        response_accuracy_expectation="No checks",
    )


def test_resolve_preferences_defaults_missing_keys_to_false() -> None:
    metadata = {"evaluations": {"flow_adherence": {"enabled": True}}}
    scenario = _make_scenario_stub(metadata=metadata, description="Fallback")

    preferences = _resolve_scenario_evaluation_preferences(scenario)  # type: ignore

    assert preferences == ScenarioEvaluationPreferences(
        action_calling=False,
        flow_adherence=True,
        response_accuracy=False,
        response_accuracy_expectation="Fallback",
    )


def test_resolve_preferences_supports_legacy_live_actions() -> None:
    metadata = {"evaluations": {"live_actions": {"enabled": True}}}
    scenario = _make_scenario_stub(metadata=metadata, description="Legacy")

    preferences = _resolve_scenario_evaluation_preferences(scenario)  # type: ignore

    assert preferences.action_calling is True


def test_resolve_preferences_falls_back_to_description_for_blank_expectation() -> None:
    metadata = {
        "evaluations": {
            "response_accuracy": {"enabled": True, "expectation": "   "},
        }
    }
    scenario = _make_scenario_stub(metadata=metadata, description="Use order summary.")

    preferences = _resolve_scenario_evaluation_preferences(scenario)  # type: ignore

    assert preferences.response_accuracy_expectation == "Use order summary."
