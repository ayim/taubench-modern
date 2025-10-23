import io
import json
import zipfile
from uuid import uuid4

import pytest
import yaml

from agent_platform.core.evals.types import Scenario
from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.content.text import ThreadTextContent
from agent_platform.core.thread.content.tool_usage import ThreadToolUsageContent


@pytest.fixture
async def storage(sqlite_storage):
    return sqlite_storage


async def _create_scenario(storage, user_id: str, agent_id: str, name: str) -> Scenario:
    scenario = Scenario(
        scenario_id=str(uuid4()),
        name=name,
        description="Sample",
        thread_id=None,
        agent_id=agent_id,
        user_id=user_id,
        messages=[
            ThreadMessage(
                role="user",
                content=[ThreadTextContent(text="Hello")],
                complete=True,
            )
        ],
        metadata={},
    )
    await storage.create_scenario(scenario)
    return scenario


async def test_export_agent_scenarios_returns_zip_with_payload(
    client, storage, seed_agents, stub_user
):
    agent = seed_agents[0]
    await _create_scenario(storage, stub_user.user_id, agent.agent_id, name="Greeting")

    response = client.get(
        "/api/v2/evals/scenarios/export",
        params={"agent_id": agent.agent_id},
    )

    assert response.status_code == 200
    content_disposition = response.headers.get("content-disposition", "")
    assert f"agent_{agent.agent_id}" in content_disposition
    assert content_disposition.endswith('.zip"')

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        namelist = archive.namelist()
        assert "metadata.yaml" in namelist
        scenario_files = [name for name in namelist if name.startswith("evals/")]
        assert len(scenario_files) == 1

        metadata = yaml.safe_load(archive.read("metadata.yaml"))
        payload = yaml.safe_load(archive.read(scenario_files[0]))

    assert metadata["files"][0]["path"] == scenario_files[0]
    assert payload["name"] == "Greeting"
    assert payload["evaluations"] == []


async def test_export_agent_scenarios_handles_empty_set(client, seed_agents):
    agent = seed_agents[1]

    response = client.get(
        "/api/v2/evals/scenarios/export",
        params={"agent_id": agent.agent_id},
    )

    assert response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        namelist = archive.namelist()
        assert "metadata.yaml" in namelist
        scenario_files = [name for name in namelist if name.startswith("evals/")]
        metadata = yaml.safe_load(archive.read("metadata.yaml"))

    assert scenario_files == []
    assert metadata["files"] == []


async def test_import_agent_scenarios_creates_new_entries(client, storage, seed_agents, stub_user):
    agent = seed_agents[0]
    expectation = "Respond accurately"

    scenario = Scenario(
        scenario_id=str(uuid4()),
        name="Support Request",
        description="Handle support query",
        thread_id=None,
        agent_id=agent.agent_id,
        user_id=stub_user.user_id,
        messages=[
            ThreadMessage(
                role="user",
                content=[ThreadTextContent(text="Hello, can you help me?")],
                complete=True,
            )
        ],
        metadata={
            "evaluations": {
                "flow_adherence": {"enabled": True},
                "response_accuracy": {"enabled": True, "expectation": expectation},
                "action_calling": {"enabled": True, "assert_all_consumed": True},
            },
            "drift_policy": {
                "tool_execution_mode": "live",
            },
        },
    )
    await storage.create_scenario(scenario)

    response = client.get(
        "/api/v2/evals/scenarios/export",
        params={"agent_id": agent.agent_id},
    )
    assert response.status_code == 200

    before_import = await storage.list_scenarios(limit=None, agent_id=agent.agent_id)

    files = {
        "file": (
            "scenarios.zip",
            response.content,
            "application/zip",
        )
    }
    import_response = client.post(
        "/api/v2/evals/scenarios/import",
        params={"agent_id": agent.agent_id},
        files=files,
    )

    assert import_response.status_code == 200
    created = import_response.json()
    assert len(created) == 1

    after_import = await storage.list_scenarios(limit=None, agent_id=agent.agent_id)
    assert len(after_import) == len(before_import) + 1

    imported_scenario_id = created[0]["scenario_id"]
    assert imported_scenario_id != scenario.scenario_id

    stored = await storage.get_scenario(imported_scenario_id)
    assert stored is not None
    assert stored.name == scenario.name
    assert stored.metadata["evaluations"]["response_accuracy"]["expectation"] == expectation
    assert stored.metadata["evaluations"]["action_calling"]["assert_all_consumed"] is True
    assert stored.metadata["drift_policy"]["tool_execution_mode"] == "live"
    assert stored.messages[0].role == "user"
    assert stored.messages[0].content[0].complete is True


async def test_import_agent_scenarios_restores_used_tools(client, storage, seed_agents, stub_user):
    agent = seed_agents[0]
    tool_definition = {
        "name": "support_tool",
        "description": "Helps with support tickets",
        "category": "action-tool",
        "input_schema": {
            "type": "object",
            "properties": {"issue": {"type": "string"}},
            "required": ["issue"],
        },
    }

    scenario = Scenario(
        scenario_id=str(uuid4()),
        name="Support Workflow",
        description="Handle support cases",
        thread_id=None,
        agent_id=agent.agent_id,
        user_id=stub_user.user_id,
        messages=[
            ThreadMessage(
                role="user",
                content=[ThreadTextContent(text="Customer cannot print")],
                complete=True,
            ),
            ThreadMessage(
                role="agent",
                content=[
                    ThreadToolUsageContent(
                        name="support_tool",
                        tool_call_id="call-1",
                        arguments_raw=json.dumps({"issue": "printer"}),
                        sub_type="action-external",
                        status="finished",
                        result=json.dumps({"status": "resolved"}),
                    )
                ],
                agent_metadata={
                    "model": "gpt-test",
                    "platform": "openai",
                    "tools": [tool_definition],
                },
                complete=True,
            ),
        ],
        metadata={},
    )
    await storage.create_scenario(scenario)

    response = client.get(
        "/api/v2/evals/scenarios/export",
        params={"agent_id": agent.agent_id},
    )
    assert response.status_code == 200

    files = {
        "file": (
            "scenarios.zip",
            response.content,
            "application/zip",
        )
    }

    import_response = client.post(
        "/api/v2/evals/scenarios/import",
        params={"agent_id": agent.agent_id},
        files=files,
    )
    assert import_response.status_code == 200

    imported_scenarios = import_response.json()
    assert imported_scenarios, "Expected at least one scenario to be imported"
    imported_scenario_id = imported_scenarios[0]["scenario_id"]

    stored = await storage.get_scenario(imported_scenario_id)
    assert stored is not None

    agent_messages = [message for message in stored.messages if message.role == "agent"]
    assert agent_messages, "Expected at least one agent message in imported scenario"
    tools_metadata = agent_messages[0].agent_metadata.get("tools")

    assert isinstance(tools_metadata, list)
    assert tools_metadata
    imported_tool = next(tool for tool in tools_metadata if tool["name"] == "support_tool")
    assert imported_tool["description"] == tool_definition["description"]
    assert imported_tool["category"] == "action-tool"
    assert imported_tool["input_schema"] == tool_definition["input_schema"]


async def test_import_agent_scenarios_rejects_invalid_archive(client, storage, seed_agents):
    agent = seed_agents[0]

    before = await storage.list_scenarios(limit=None, agent_id=agent.agent_id)

    response = client.post(
        "/api/v2/evals/scenarios/import",
        params={"agent_id": agent.agent_id},
        files={"file": ("invalid.zip", b"not-a-zip", "application/zip")},
    )

    assert response.status_code == 400

    after = await storage.list_scenarios(limit=None, agent_id=agent.agent_id)
    assert len(after) == len(before)
