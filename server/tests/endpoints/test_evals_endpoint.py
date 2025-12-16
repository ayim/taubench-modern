import io
import json
import zipfile
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import yaml
from fastapi import UploadFile

from agent_platform.core.evals.types import (
    ExecutionState,
    FlowAdherenceResult,
    ResponseAccuracyResult,
    Scenario,
    TrialStatus,
)
from agent_platform.core.payloads import UploadFilePayload
from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.content.attachment import ThreadAttachmentContent
from agent_platform.core.thread.content.text import ThreadTextContent
from agent_platform.core.thread.content.tool_usage import ThreadToolUsageContent
from agent_platform.core.thread.thread import Thread
from agent_platform.server.evals.run_scenario import (
    _copy_scenario_files_to_run_thread,
    _rewrite_attachment_handles,
)
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


def _assert_trial_statuses(payload: dict, expected_runs: int, expected_trials: int) -> None:
    statuses = payload.get("trial_statuses")
    assert isinstance(statuses, list)
    assert len(statuses) == expected_runs
    for status_entry in statuses:
        assert status_entry["scenario_run_id"]
        assert status_entry["scenario_id"]
        trials = status_entry.get("trials")
        assert isinstance(trials, list)
        assert len(trials) == expected_trials
        for trial in trials:
            assert trial["trial_id"]
            assert isinstance(trial["index_in_run"], int)
            assert trial["status"] in {status.value for status in TrialStatus}
            assert "progress_classification" in trial
            assert "last_progress_at" in trial


async def test_export_agent_scenarios_returns_zip_with_payload(client, storage, seed_agents, stub_user):
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


async def test_export_agent_scenarios_includes_scenario_files(client, storage, seed_agents, stub_user):
    FileManagerService.reset()
    try:
        agent = seed_agents[0]
        scenario = Scenario(
            scenario_id=str(uuid4()),
            name="With attachment",
            description="Scenario with scenario file",
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
            metadata={},
        )
        await storage.create_scenario(scenario)

        file_manager = FileManagerService.get_instance(storage)
        file_bytes = b"id,name\n1,Alice\n"
        upload = UploadFile(filename="data.csv", file=io.BytesIO(file_bytes))
        try:
            uploaded_files = await file_manager.upload(
                [UploadFilePayload(file=upload)],
                scenario,
                stub_user.user_id,
            )
        finally:
            await upload.close()

        uploaded_file = uploaded_files[0]

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
    finally:
        FileManagerService.reset()


def test_rewrite_attachment_handles_updates_uris():
    old_id = str(uuid4())
    new_id = str(uuid4())
    message = ThreadMessage(
        role="user",
        content=[
            ThreadAttachmentContent(
                name="notes.txt",
                mime_type="text/plain",
                uri=f"agent-server-file://{old_id}",
            )
        ],
        complete=True,
    )

    updated = _rewrite_attachment_handles([message], {old_id: new_id})

    assert updated is True
    attachment = next(content for content in message.content if isinstance(content, ThreadAttachmentContent))
    assert attachment.uri == f"agent-server-file://{new_id}"


async def test_create_scenario_copies_thread_files(client, storage, seed_agents, stub_user):
    FileManagerService.reset()
    try:
        agent = seed_agents[0]
        thread = Thread(
            user_id=stub_user.user_id,
            agent_id=agent.agent_id,
            name="Source thread",
        )
        await storage.upsert_thread(stub_user.user_id, thread)

        file_manager = FileManagerService.get_instance(storage)
        file_bytes = b"thread-data"
        upload = UploadFile(filename="thread.txt", file=io.BytesIO(file_bytes))
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
        await storage.overwrite_thread_messages(thread.thread_id, [attachment_message])

        response = client.post(
            "/api/v2/evals/scenarios",
            json={
                "name": "Copied scenario",
                "description": "Should include files",
                "thread_id": thread.thread_id,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        scenario_id = payload["scenario_id"]

        scenario_files = await storage.get_scenario_files(scenario_id, stub_user.user_id)
        assert len(scenario_files) == 1
        scenario_file = scenario_files[0]
        assert scenario_file.file_ref == uploaded_file.file_ref

        copied_bytes = await file_manager.read_file_contents(
            scenario_file.file_id,
            stub_user.user_id,
        )
        assert copied_bytes == file_bytes

        stored_scenario = await storage.get_scenario(scenario_id)
        assert stored_scenario is not None
        stored_attachments = [
            content
            for message in stored_scenario.messages
            for content in message.content
            if isinstance(content, ThreadAttachmentContent)
        ]
        assert len(stored_attachments) == 1
        assert stored_attachments[0].uri == f"agent-server-file://{scenario_file.file_id}"
    finally:
        FileManagerService.reset()


async def test_list_scenarios_endpoint_omits_messages(client, storage, seed_agents, stub_user):
    agent = seed_agents[0]
    scenario = Scenario(
        scenario_id=str(uuid4()),
        name="Verbose scenario",
        description="Contains messages that should not be returned",
        thread_id=None,
        agent_id=agent.agent_id,
        user_id=stub_user.user_id,
        messages=[
            ThreadMessage(
                role="user",
                content=[ThreadTextContent(text="How are you?")],
                complete=True,
            ),
            ThreadMessage(
                role="agent",
                content=[ThreadTextContent(text="All good here!")],
                complete=True,
            ),
        ],
        metadata={},
    )
    await storage.create_scenario(scenario)

    response = client.get(
        "/api/v2/evals/scenarios",
        params={"agent_id": agent.agent_id},
    )
    assert response.status_code == 200
    payload = response.json()

    assert len(payload) == 1
    assert payload[0]["scenario_id"] == scenario.scenario_id
    assert payload[0]["messages"] == []

    stored = await storage.get_scenario(scenario.scenario_id)
    assert stored is not None
    assert len(stored.messages) == 2


async def test_list_scenarios_can_include_messages(storage, seed_agents, stub_user):
    agent = seed_agents[0]
    scenario = Scenario(
        scenario_id=str(uuid4()),
        name="Full history scenario",
        description="Used to verify include_messages=True",
        thread_id=None,
        agent_id=agent.agent_id,
        user_id=stub_user.user_id,
        messages=[
            ThreadMessage(
                role="user",
                content=[ThreadTextContent(text="Can you help me?")],
                complete=True,
            )
        ],
        metadata={},
    )
    await storage.create_scenario(scenario)

    default_list = await storage.list_scenarios(
        limit=None,
        agent_id=agent.agent_id,
    )
    assert default_list
    assert default_list[0].messages == []

    with_messages = await storage.list_scenarios(
        limit=None,
        agent_id=agent.agent_id,
        include_messages=True,
    )
    assert with_messages
    assert len(with_messages[0].messages) == 1
    assert with_messages[0].messages[0].content[0].text == "Can you help me?"


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


async def test_import_agent_scenarios_restores_attachments(client, storage, seed_agents, stub_user):
    agent = seed_agents[0]

    scenario = Scenario(
        scenario_id=str(uuid4()),
        name="Scenario with files",
        description="Contains thread attachments",
        thread_id=None,
        agent_id=agent.agent_id,
        user_id=stub_user.user_id,
        messages=[],
        metadata={},
    )
    scenario = await storage.create_scenario(scenario)

    file_manager = FileManagerService.get_instance(storage)
    file_bytes = b"hello,world\n"
    upload = UploadFile(filename="report.csv", file=io.BytesIO(file_bytes))
    try:
        uploaded_files = await file_manager.upload(
            [UploadFilePayload(file=upload)],
            scenario,
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

    await storage.update_scenario_messages(
        scenario.scenario_id,
        [attachment_message],
    )

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
    imported_payload = import_response.json()
    assert imported_payload

    imported_scenario_id = imported_payload[0]["scenario_id"]
    assert imported_scenario_id != scenario.scenario_id

    scenario_files = await storage.get_scenario_files(imported_scenario_id, stub_user.user_id)
    assert len(scenario_files) == 1

    imported_file = scenario_files[0]
    assert imported_file.file_ref
    assert imported_file.mime_type == uploaded_file.mime_type

    imported_bytes = await file_manager.read_file_contents(
        imported_file.file_id,
        stub_user.user_id,
    )
    assert imported_bytes == file_bytes

    stored = await storage.get_scenario(imported_scenario_id)
    assert stored is not None
    attachment_contents = [
        content
        for message in stored.messages
        for content in message.content
        if isinstance(content, ThreadAttachmentContent)
    ]
    assert attachment_contents
    expected_uris = {f"agent-server-file://{file.file_id}" for file in scenario_files}
    for content in attachment_contents:
        assert content.uri in expected_uris
        assert uploaded_file.file_id not in content.uri


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


@pytest.mark.asyncio
async def test_copy_scenario_files_to_run_thread_prefers_scenario_files(storage, seed_agents, stub_user):
    FileManagerService.reset()
    try:
        file_manager = FileManagerService.get_instance(storage)

        agent = seed_agents[0]
        scenario = Scenario(
            scenario_id=str(uuid4()),
            name="Scenario attachments",
            description="Scenario owned files",
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
            metadata={},
        )
        await storage.create_scenario(scenario)

        file_bytes = b"scenario-data"
        upload = UploadFile(filename="notes.txt", file=io.BytesIO(file_bytes))
        try:
            uploaded_files = await file_manager.upload(
                [UploadFilePayload(file=upload)],
                scenario,
                stub_user.user_id,
            )
        finally:
            await upload.close()

        uploaded_file = uploaded_files[0]

        destination_thread = Thread(
            user_id=stub_user.user_id,
            agent_id=agent.agent_id,
            name="Destination thread",
        )
        await storage.upsert_thread(stub_user.user_id, destination_thread)

        file_map = await _copy_scenario_files_to_run_thread(
            storage=storage,
            scenario=scenario,
            destination_thread=destination_thread,
            destination_user_id=stub_user.user_id,
        )

        thread_files = await storage.get_thread_files(destination_thread.thread_id, stub_user.user_id)
        assert len(thread_files) == 1

        copied_file = thread_files[0]
        assert copied_file.file_ref == uploaded_file.file_ref
        copied_bytes = await file_manager.read_file_contents(
            copied_file.file_id,
            stub_user.user_id,
        )
        assert copied_bytes == file_bytes
        assert file_map == {uploaded_file.file_id: copied_file.file_id}
    finally:
        FileManagerService.reset()


@pytest.mark.asyncio
async def test_copy_scenario_files_to_run_thread_ignores_thread_files(storage, seed_agents, stub_user):
    FileManagerService.reset()
    try:
        file_manager = FileManagerService.get_instance(storage)

        agent = seed_agents[0]
        source_thread = Thread(
            user_id=stub_user.user_id,
            agent_id=agent.agent_id,
            name="Source thread",
        )
        await storage.upsert_thread(stub_user.user_id, source_thread)

        thread_bytes = b"thread-attachment"
        upload = UploadFile(filename="fallback.txt", file=io.BytesIO(thread_bytes))
        try:
            await file_manager.upload(
                [UploadFilePayload(file=upload)],
                source_thread,
                stub_user.user_id,
            )
        finally:
            await upload.close()

        scenario = Scenario(
            scenario_id=str(uuid4()),
            name="Scenario with thread files",
            description="Fallback scenario",
            thread_id=source_thread.thread_id,
            agent_id=agent.agent_id,
            user_id=stub_user.user_id,
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

        destination_thread = Thread(
            user_id=stub_user.user_id,
            agent_id=agent.agent_id,
            name="Destination thread",
        )
        await storage.upsert_thread(stub_user.user_id, destination_thread)

        file_map = await _copy_scenario_files_to_run_thread(
            storage=storage,
            scenario=scenario,
            destination_thread=destination_thread,
            destination_user_id=stub_user.user_id,
        )

        thread_files = await storage.get_thread_files(destination_thread.thread_id, stub_user.user_id)
        assert not thread_files
        assert not file_map
    finally:
        FileManagerService.reset()


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


async def test_create_agent_batch_run_creates_runs_for_all_scenarios(client, storage, seed_agents, stub_user):
    agent = seed_agents[0]
    await _create_scenario(storage, stub_user.user_id, agent.agent_id, name="Scenario 1")
    await _create_scenario(storage, stub_user.user_id, agent.agent_id, name="Scenario 2")

    response = client.post(
        f"/api/v2/evals/agents/{agent.agent_id}/batches",
        json={"num_trials": 2},
    )

    assert response.status_code == 200
    batch = response.json()
    assert batch["status"] == "RUNNING"
    assert batch["statistics"]["total_scenarios"] == 2

    runs = await storage.list_scenario_runs_for_batch(batch["batch_run_id"])
    assert len(runs) == 2
    assert all(run.batch_run_id == batch["batch_run_id"] for run in runs)

    for run in runs:
        trials = await storage.list_scenario_run_trials(run.scenario_run_id)
        assert len(trials) == 2
        assert all(trial.status == TrialStatus.PENDING for trial in trials)


async def test_create_agent_batch_run_returns_trial_statuses(client, storage, seed_agents, stub_user):
    agent = seed_agents[0]
    await _create_scenario(storage, stub_user.user_id, agent.agent_id, name="Scenario 1")
    await _create_scenario(storage, stub_user.user_id, agent.agent_id, name="Scenario 2")

    response = client.post(
        f"/api/v2/evals/agents/{agent.agent_id}/batches",
        json={"num_trials": 2},
    )

    assert response.status_code == 200
    batch = response.json()

    _assert_trial_statuses(batch, expected_runs=2, expected_trials=2)


async def test_get_agent_batch_run_reports_statistics(client, storage, seed_agents, stub_user):
    agent = seed_agents[0]
    await _create_scenario(storage, stub_user.user_id, agent.agent_id, name="Happy path")
    await _create_scenario(storage, stub_user.user_id, agent.agent_id, name="Sad path")

    response = client.post(
        f"/api/v2/evals/agents/{agent.agent_id}/batches",
        json={"num_trials": 1},
    )
    assert response.status_code == 200
    batch = response.json()

    runs = await storage.list_scenario_runs_for_batch(batch["batch_run_id"])
    assert len(runs) == 2

    completed_trial = (await storage.list_scenario_run_trials(runs[0].scenario_run_id))[0]
    failed_trial = (await storage.list_scenario_run_trials(runs[1].scenario_run_id))[0]

    await storage.update_trial_status(
        completed_trial.trial_id,
        stub_user.user_id,
        TrialStatus.COMPLETED,
    )
    await storage.update_trial_evaluation_results(
        completed_trial.trial_id,
        [FlowAdherenceResult(explanation="ok", score=1, passed=True)],
    )

    await storage.update_trial_status(
        failed_trial.trial_id,
        stub_user.user_id,
        TrialStatus.ERROR,
        error="boom",
    )
    await storage.update_trial_evaluation_results(
        failed_trial.trial_id,
        [ResponseAccuracyResult(explanation="nope", score=0, passed=False)],
    )

    result = client.get(f"/api/v2/evals/agents/{agent.agent_id}/batches/{batch['batch_run_id']}")
    assert result.status_code == 200
    batch_status = result.json()

    assert batch_status["status"] == "COMPLETED"
    stats = batch_status["statistics"]
    assert stats["completed_scenarios"] == 1
    assert stats["failed_scenarios"] == 1
    assert stats["completed_trials"] == 1
    assert stats["failed_trials"] == 1

    eval_totals = stats["evaluation_totals"]
    assert eval_totals["flow_adherence"]["passed"] == 1
    assert eval_totals["response_accuracy"]["total"] == 1
    assert eval_totals["response_accuracy"]["passed"] == 0


async def test_get_agent_batch_run_returns_trial_statuses(client, storage, seed_agents, stub_user):
    agent = seed_agents[0]
    await _create_scenario(storage, stub_user.user_id, agent.agent_id, name="Scenario 1")

    response = client.post(
        f"/api/v2/evals/agents/{agent.agent_id}/batches",
        json={"num_trials": 1},
    )
    assert response.status_code == 200
    batch = response.json()
    runs = await storage.list_scenario_runs_for_batch(batch["batch_run_id"])
    assert runs

    trial = (await storage.list_scenario_run_trials(runs[0].scenario_run_id))[0]
    await storage.update_trial_status(
        trial.trial_id,
        stub_user.user_id,
        TrialStatus.COMPLETED,
    )

    result = client.get(f"/api/v2/evals/agents/{agent.agent_id}/batches/{batch['batch_run_id']}")
    assert result.status_code == 200
    payload = result.json()

    _assert_trial_statuses(payload, expected_runs=1, expected_trials=1)
    status_entry = payload["trial_statuses"][0]
    assert status_entry["scenario_run_id"] == runs[0].scenario_run_id
    assert status_entry["trials"][0]["status"] == TrialStatus.COMPLETED.value


async def test_retry_after_at_persists_through_api(client, storage, seed_agents, stub_user):
    agent = seed_agents[0]
    scenario = await _create_scenario(storage, stub_user.user_id, agent.agent_id, name="Throttle me")

    run_response = client.post(
        f"/api/v2/evals/scenarios/{scenario.scenario_id}/runs",
        json={"num_trials": 1},
    )
    assert run_response.status_code == 200
    run_payload = run_response.json()
    scenario_run_id = run_payload["scenario_run_id"]
    trial_id = run_payload["trials"][0]["trial_id"]

    await storage.update_trial_status(
        trial_id,
        stub_user.user_id,
        TrialStatus.EXECUTING,
    )

    retry_after_at = datetime.now(UTC) + timedelta(seconds=90)
    metadata = {"rescheduled": True}
    await storage.requeue_trial(
        trial_id,
        reason="Rate limited",
        metadata=metadata,
        retry_after_at=retry_after_at,
        reschedule_attempts=3,
    )

    run_detail = client.get(f"/api/v2/evals/scenarios/{scenario.scenario_id}/runs/{scenario_run_id}")
    assert run_detail.status_code == 200
    run_detail_payload = run_detail.json()
    trial_payload = run_detail_payload["trials"][0]

    assert trial_payload["status"] == "PENDING"
    serialized_retry_after = trial_payload["retry_after_at"]
    assert serialized_retry_after.replace("Z", "+00:00") == retry_after_at.isoformat()
    assert trial_payload["reschedule_attempts"] == 3
    assert trial_payload["error_message"] == "Rate limited"
    assert trial_payload["metadata"] == metadata


async def test_latest_scenario_run_includes_progress_classification(client, storage, seed_agents, stub_user):
    agent = seed_agents[0]
    scenario = await _create_scenario(storage, stub_user.user_id, agent.agent_id, name="Stalled run")

    run_response = client.post(
        f"/api/v2/evals/scenarios/{scenario.scenario_id}/runs",
        json={"num_trials": 1},
    )
    assert run_response.status_code == 200
    run_payload = run_response.json()
    trial_id = run_payload["trials"][0]["trial_id"]

    await storage.update_trial_status(
        trial_id,
        stub_user.user_id,
        TrialStatus.EXECUTING,
    )

    execution_state = ExecutionState()
    execution_state.last_progress_at = datetime.now(UTC) - timedelta(seconds=1_200)
    await storage.update_trial_execution(trial_id, execution_state)

    latest_run_response = client.get(f"/api/v2/evals/scenarios/{scenario.scenario_id}/runs/latest")
    assert latest_run_response.status_code == 200
    trial_payload = latest_run_response.json()["trials"][0]
    assert trial_payload["progress_classification"] == "stalled"


async def test_cancel_agent_batch_run_marks_trials_canceled(client, storage, seed_agents, stub_user):
    agent = seed_agents[0]
    await _create_scenario(storage, stub_user.user_id, agent.agent_id, name="Alpha")
    await _create_scenario(storage, stub_user.user_id, agent.agent_id, name="Beta")

    batch_response = client.post(
        f"/api/v2/evals/agents/{agent.agent_id}/batches",
        json={"num_trials": 2},
    )
    assert batch_response.status_code == 200
    batch = batch_response.json()

    runs = await storage.list_scenario_runs_for_batch(batch["batch_run_id"])
    assert runs

    completed_run_trials = await storage.list_scenario_run_trials(runs[0].scenario_run_id)
    for trial in completed_run_trials:
        await storage.update_trial_status(
            trial.trial_id,
            stub_user.user_id,
            TrialStatus.COMPLETED,
        )

    response = client.delete(f"/api/v2/evals/agents/{agent.agent_id}/batches/{batch['batch_run_id']}")
    assert response.status_code == 200
    canceled_batch = response.json()

    assert canceled_batch["status"] == "CANCELED"
    stats = canceled_batch["statistics"]
    assert stats["total_scenarios"] == len(runs)
    assert stats["failed_scenarios"] == len(runs) - 1
    assert stats["completed_scenarios"] == 1
    assert stats["total_trials"] == len(runs) * 2
    assert stats["completed_trials"] == len(completed_run_trials)

    for index, run in enumerate(runs):
        trials = await storage.list_scenario_run_trials(run.scenario_run_id)
        expected_status = TrialStatus.COMPLETED if index == 0 else TrialStatus.CANCELED
        assert all(trial.status == expected_status for trial in trials)
