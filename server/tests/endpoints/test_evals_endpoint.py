import io
import json
import zipfile
from uuid import uuid4

import pytest
import yaml
from fastapi import UploadFile

from agent_platform.core.evals.types import Scenario
from agent_platform.core.payloads import UploadFilePayload
from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.content.attachment import ThreadAttachmentContent
from agent_platform.core.thread.content.text import ThreadTextContent
from agent_platform.core.thread.content.tool_usage import ThreadToolUsageContent
from agent_platform.core.thread.thread import Thread
from agent_platform.server.file_manager import FileManagerService


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
        assert "agent_id" not in metadata
        payload = yaml.safe_load(archive.read(scenario_files[0]))

    assert metadata["files"][0]["path"] == scenario_files[0]
    assert payload["name"] == "Greeting"
    assert payload["evaluations"] == []
    assert metadata["files"][0]["attachments"] == []
    assert "scenario_id" not in metadata["files"][0]


async def test_export_agent_scenarios_includes_thread_files(
    client, storage, seed_agents, stub_user
):
    agent = seed_agents[0]
    thread = Thread(
        user_id=stub_user.user_id,
        agent_id=agent.agent_id,
        name="Source thread",
    )
    await storage.upsert_thread(stub_user.user_id, thread)

    file_manager = FileManagerService.get_instance(storage)
    file_bytes = b"id,name\n1,Alice\n"
    upload = UploadFile(filename="data.csv", file=io.BytesIO(file_bytes))
    try:
        uploaded_files = await file_manager.upload(
            [UploadFilePayload(file=upload)],
            thread,
            stub_user.user_id,
        )
    finally:
        await upload.close()

    uploaded_file = uploaded_files[0]

    attachment_message = ThreadMessage(
        role="user",
        content=[
            ThreadAttachmentContent(
                name=uploaded_file.file_ref,
                mime_type=uploaded_file.mime_type,
                uri=f"agent-server-file://{uploaded_file.file_id}",
            )
        ],
        complete=True,
    )

    scenario = Scenario(
        scenario_id=str(uuid4()),
        name="With attachment",
        description="Scenario with thread file",
        thread_id=thread.thread_id,
        agent_id=agent.agent_id,
        user_id=stub_user.user_id,
        messages=[attachment_message],
        metadata={},
    )
    await storage.create_scenario(scenario)

    response = client.get(
        "/api/v2/evals/scenarios/export",
        params={"agent_id": agent.agent_id},
    )

    assert response.status_code == 200

    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        namelist = archive.namelist()
        metadata = yaml.safe_load(archive.read("metadata.yaml"))
        assert "agent_id" not in metadata
        attachment_entries = [name for name in namelist if name.startswith("thread_files/")]
        assert attachment_entries
        exported_bytes = archive.read(attachment_entries[0])

    assert exported_bytes == file_bytes

    metadata_entry = metadata["files"][0]
    assert metadata_entry["attachments"]
    assert "scenario_id" not in metadata_entry
    attachment_meta = metadata_entry["attachments"][0]
    assert attachment_meta["path"] == attachment_entries[0]
    assert attachment_meta["file_ref"] == uploaded_file.file_ref
    assert "file_id" not in attachment_meta


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
        assert "agent_id" not in metadata

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


async def test_update_scenario_persists_changes(client, storage, seed_agents, stub_user):
    agent = seed_agents[0]
    scenario = Scenario(
        scenario_id=str(uuid4()),
        name="Original",
        description="Original description",
        thread_id=None,
        agent_id=agent.agent_id,
        user_id=stub_user.user_id,
        messages=[
            ThreadMessage(
                role="user",
                content=[ThreadTextContent(text="Hello")],
                complete=True,
            )
        ],
        metadata={
            "evaluations": {
                "response_accuracy": {
                    "enabled": True,
                    "expectation": "Stay polite.",
                }
            },
            "drift_policy": {"tool_execution_mode": "live"},
        },
    )
    await storage.create_scenario(scenario)

    payload = {
        "name": "Updated",
        "description": "Updated description",
        "evaluation_criteria": [
            {"type": "action_calling"},
            {"type": "flow_adherence"},
            {"type": "response_accuracy", "expectation": "Handle returns."},
        ],
    }

    response = client.patch(
        f"/api/v2/evals/scenarios/{scenario.scenario_id}",
        json=payload,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "Updated"
    assert body["description"] == "Updated description"

    stored = await storage.get_scenario(scenario_id=scenario.scenario_id)
    assert stored is not None
    assert stored.name == "Updated"
    assert stored.description == "Updated description"

    metadata = stored.metadata or {}
    evaluations = metadata.get("evaluations", {})
    response_accuracy = evaluations.get("response_accuracy", {})
    assert response_accuracy.get("expectation") == "Handle returns."
    assert evaluations.get("action_calling", {}).get("enabled") is True
    drift_policy = metadata.get("drift_policy", {})
    assert "tool_execution_mode" not in drift_policy
