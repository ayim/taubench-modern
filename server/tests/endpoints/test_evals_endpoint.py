import io
import zipfile
from uuid import uuid4

import pytest
import yaml

from agent_platform.core.evals.types import Scenario
from agent_platform.core.thread.base import ThreadMessage
from agent_platform.core.thread.content.text import ThreadTextContent


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
