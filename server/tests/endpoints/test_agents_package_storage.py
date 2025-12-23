"""Integration tests for agent package endpoints with real storage.

This module tests storage behavior of agent package endpoints using real SQLite database,
focusing on cleanup and error handling scenarios that require actual database verification.
"""

import typing
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from agent_platform.core.runbook.runbook import Runbook
from agent_platform.server.api.private_v2.package import upsert_agent_from_package
from agent_platform.server.storage.errors import AgentNotFoundError

if typing.TYPE_CHECKING:
    from agent_platform.server.storage.sqlite import SQLiteStorage
    from server.tests.storage.sample_model_creator import SampleModelCreator


@pytest.mark.asyncio
async def test_create_agent_cleanup_on_sdm_failure(
    sqlite_storage: "SQLiteStorage",
    sqlite_model_creator: "SampleModelCreator",
    monkeypatch,
):
    """Test that agent is cleaned up if SDM import fails after upsert_agent.

    This test verifies the cleanup behavior when upsert_semantic_data_models fails:
    - For "create" operation: Agent should be deleted from database
    - For "update" operation: Agent should be preserved (not deleted)
    """
    from agent_platform.server.api.private_v2.package import upserts as package_upserts

    # Get real user from model creator
    user = await sqlite_model_creator.get_authed_user()

    # Get sample payload and mock handler from model creator
    sample_agent_package_payload = sqlite_model_creator.obtain_sample_agent_package_payload()
    mock_agent_package_handler = sqlite_model_creator.obtain_mock_agent_package_handler()

    # Setup: use fresh ID for create case
    aid = str(uuid4())

    # Force SDM import to fail
    mock_upsert_semantic_data_models = AsyncMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr(
        package_upserts,
        "upsert_semantic_data_models",
        mock_upsert_semantic_data_models,
    )

    # Mock AgentPackageHandler creation
    monkeypatch.setattr(
        package_upserts.AgentPackageHandler,
        "from_url",
        AsyncMock(return_value=mock_agent_package_handler),
    )

    # Execute and expect failure
    with pytest.raises(RuntimeError, match="boom"):
        await upsert_agent_from_package(
            user=user,
            aid=aid,
            payload=sample_agent_package_payload,
            storage=sqlite_storage,
        )

    # Agent should be deleted - verify it doesn't exist
    with pytest.raises(AgentNotFoundError):
        await sqlite_storage.get_agent(user.user_id, aid)


@pytest.mark.asyncio
async def test_update_agent_cleanup_on_sdm_failure(
    sqlite_storage: "SQLiteStorage",
    sqlite_model_creator: "SampleModelCreator",
    monkeypatch,
):
    """Test that agent is cleaned up if SDM import fails after upsert_agent.

    This test verifies the cleanup behavior when upsert_semantic_data_models fails:
    - For "create" operation: Agent should be deleted from database
    - For "update" operation: Agent should be preserved (not deleted)
    """
    from agent_platform.server.api.private_v2.package import upserts as package_upserts

    # Get real user from model creator
    user = await sqlite_model_creator.get_authed_user()

    # Get sample payload and mock handler from model creator
    sample_agent_package_payload = sqlite_model_creator.obtain_sample_agent_package_payload()
    mock_agent_package_handler = sqlite_model_creator.obtain_mock_agent_package_handler(
        custom_spec={"runbook_text": "updated runbook text"},
    )

    # Setup: Create agent for update case
    existing_agent = await sqlite_model_creator.obtain_sample_agent("Existing Agent")
    # Set an "original" runbook, save it back into Storage.
    existing_agent = existing_agent.copy(
        runbook_structured=Runbook(
            raw_text="original runbook text",
            content=[],
        )
    )
    await sqlite_storage.upsert_agent(user.user_id, existing_agent)
    aid = existing_agent.agent_id

    # Force SDM import to fail
    mock_upsert_semantic_data_models = AsyncMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr(
        package_upserts,
        "upsert_semantic_data_models",
        mock_upsert_semantic_data_models,
    )

    # Mock AgentPackageHandler creation
    monkeypatch.setattr(
        package_upserts.AgentPackageHandler,
        "from_url",
        AsyncMock(return_value=mock_agent_package_handler),
    )

    # Execute and expect failure
    with pytest.raises(RuntimeError, match="boom"):
        await upsert_agent_from_package(
            user=user,
            aid=aid,
            payload=sample_agent_package_payload,
            storage=sqlite_storage,
        )

    # Agent should be preserved on update failure
    try:
        agent = await sqlite_storage.get_agent(user.user_id, aid)
        # If we get here, agent was preserved - this is correct behavior
        assert agent is not None
        assert agent.agent_id == aid
        assert agent.runbook_structured.raw_text == "original runbook text"
    except AgentNotFoundError:
        # If we get here, agent was deleted - this indicates a bug
        pytest.fail(
            "Agent was deleted on update failure. According to the cleanup logic, "
            "agents should be preserved when they existed before the operation."
        )
