from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from agent_platform.core.agent_package.handler.action_package import ActionPackageHandler
from agent_platform.core.agent_package.handler.agent_package import AgentPackageHandler
from agent_platform.core.agent_package.metadata.agent_metadata import AgentPackageMetadata
from agent_platform.core.agent_package.spec import AgentSpec, SpecAgent
from agent_platform.core.errors.base import PlatformHTTPError


class TestAgentPackageHandler:
    @pytest.mark.asyncio
    async def test_agent_package_handler_missing_agent_spec(self, test_agent_package_provider):
        zip_data = test_agent_package_provider("fail-missing-agent-spec.zip")

        with pytest.raises(PlatformHTTPError, match="missing in Agent Package"):
            await AgentPackageHandler.from_bytes(zip_data)

    async def test_agent_package_handler_invalid_agent_spec(self, test_agent_package_provider):
        zip_data = test_agent_package_provider("fail-invalid-agent-spec.zip")

        with pytest.raises(ValidationError):
            await AgentPackageHandler.from_bytes(zip_data)

    @pytest.mark.asyncio
    async def test_agent_package_read_spec(self, test_agent_package_provider):
        zip_data = test_agent_package_provider("pass-call-center-planner.zip")

        with await AgentPackageHandler.from_bytes(zip_data) as handler:
            spec = await handler.read_agent_spec()

            assert spec is not None

            assert isinstance(spec, AgentSpec)
            assert spec.agent_package.agents[0].name == "Call Center Planner"

    @pytest.mark.asyncio
    async def test_agent_package_validate_package_contents_ok(self, test_agent_package_provider):
        zip_data = test_agent_package_provider("pass-call-center-planner.zip")

        with await AgentPackageHandler.from_bytes(zip_data) as handler:
            await handler.validate_package_contents()

    @pytest.mark.asyncio
    async def test_agent_package_get_spec_agent_returns_first_agent(self, test_agent_package_provider):
        zip_data = test_agent_package_provider("pass-call-center-planner.zip")

        with await AgentPackageHandler.from_bytes(zip_data) as handler:
            agent = await handler.get_spec_agent()

            assert agent is not None
            assert isinstance(agent, SpecAgent)
            assert agent.name == "Call Center Planner"

    @pytest.mark.asyncio
    async def test_agent_package_read_agent_spec_is_cached(self, test_agent_package_provider, monkeypatch):
        """
        read_agent_spec() caches the parsed AgentSpec to avoid re-reading agent-spec.yaml.
        """
        zip_data = test_agent_package_provider("pass-call-center-planner.zip")

        with await AgentPackageHandler.from_bytes(zip_data) as handler:
            original_read_file = handler.read_file
            spy_read_file = AsyncMock(side_effect=original_read_file)
            monkeypatch.setattr(handler, "read_file", spy_read_file)

            spec1 = await handler.read_agent_spec()
            spec2 = await handler.read_agent_spec()

            assert spec1 is spec2

            # read_agent_spec() is called when validating the Package in from_bytes,
            # therefore we expect call count to be zero after the package is created.
            assert spy_read_file.call_count == 0

    @pytest.mark.asyncio
    async def test_agent_package_read_metadata_ok(self, test_agent_package_provider):
        zip_data = test_agent_package_provider("pass-call-center-planner.zip")

        with await AgentPackageHandler.from_bytes(zip_data) as handler:
            metadata = await handler.read_metadata()

            assert metadata is not None
            assert isinstance(metadata, AgentPackageMetadata)

    @pytest.mark.asyncio
    async def test_agent_package_read_runbook_returns_text(self, test_agent_package_provider):
        zip_data = test_agent_package_provider("pass-call-center-planner.zip")

        with await AgentPackageHandler.from_bytes(zip_data) as handler:
            runbook_text = await handler.read_runbook()

            assert isinstance(runbook_text, str)
            assert len(runbook_text) > 0

    @pytest.mark.asyncio
    async def test_agent_package_read_conversation_guide_raw_when_not_set(self, test_agent_package_provider):
        zip_data = test_agent_package_provider("pass-document-extraction-agent.zip")

        with await AgentPackageHandler.from_bytes(zip_data) as handler:
            result = await handler.read_conversation_guide_raw()
            assert result is None

    @pytest.mark.asyncio
    async def test_agent_package_read_conversation_guide_raw_when_set(self, test_agent_package_provider):
        zip_data = test_agent_package_provider("pass-call-center-planner.zip")

        with await AgentPackageHandler.from_bytes(zip_data) as handler:
            result = await handler.read_conversation_guide_raw()

            # @TODO:
            # Extend assertions once serializing conversation guide into a model is merged into main
            assert result is not None

    @pytest.mark.asyncio
    async def test_agent_package_read_action_packages(self, test_agent_package_provider, monkeypatch):
        zip_data = test_agent_package_provider("pass-call-center-planner.zip")

        with await AgentPackageHandler.from_bytes(zip_data) as handler:
            agent = await handler.get_spec_agent()

            assert len(agent.action_packages) == 3
            assert agent.action_packages[0] is not None
            assert agent.action_packages[0].path is not None

            action_package_bytes = await handler.read_action_package_zip_raw(agent.action_packages[0].path)

            with await ActionPackageHandler.from_bytes(action_package_bytes) as action_package_handler:
                spec_contents = await action_package_handler.read_package_spec_raw()
                assert spec_contents is not None

    @pytest.mark.asyncio
    async def test_agent_package_read_semantic_data_model_raw_builds_semantic_models_path(
        self, test_agent_package_provider, monkeypatch
    ):
        zip_data = test_agent_package_provider("pass-test-sdm-agent.zip")

        with await AgentPackageHandler.from_bytes(zip_data) as handler:
            agent = await handler.get_spec_agent()

            assert agent.semantic_data_models is not None
            assert len(agent.semantic_data_models) == 1
            result = await handler.read_semantic_data_model_raw(agent.semantic_data_models[0].name)

            # @TODO:
            # Extend assertions once serializing SDMs into a model is merged into main
            assert result is not None
