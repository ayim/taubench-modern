"""Tests for build_agent_package function."""

import json
import zipfile
from collections.abc import AsyncGenerator
from io import BytesIO

import pytest

from agent_platform.core.actions.action_package import ActionPackage
from agent_platform.core.agent import Agent
from agent_platform.core.agent.agent_architecture import AgentArchitecture
from agent_platform.core.agent_package.build import AgentPackageBuilder
from agent_platform.core.agent_package.config import AgentPackageConfig
from agent_platform.core.agent_package.create import create_agent_project_zip
from agent_platform.core.agent_package.handler.agent_package import AgentPackageHandler
from agent_platform.core.agent_package.spec import AgentPackageSpec
from agent_platform.core.runbook.runbook import Runbook
from agent_platform.core.selected_tools import SelectedTools
from agent_platform.core.utils.secret_str import SecretString


async def collect_async_generator(gen: AsyncGenerator[bytes, None]) -> bytes:
    """Collect all bytes from an async generator into a single bytes object."""
    result = b""
    async for chunk in gen:
        result += chunk
    return result


async def build_agent_package_from_project_zip(project_zip_bytes: bytes) -> bytes:
    """Build an agent package from a project zip using the AgentPackageBuilder.

    Args:
        project_zip_bytes: The project zip bytes.

    Returns:
        The agent package bytes.
    """
    project_handler = await AgentPackageHandler.from_bytes(project_zip_bytes)
    builder = AgentPackageBuilder(project_handler)
    try:
        agent_package_stream = await builder.build()
        return await collect_async_generator(agent_package_stream)
    finally:
        await builder.__aexit__(None, None, None)


def create_minimal_agent(**overrides) -> Agent:
    """Create a minimal Agent instance for testing."""
    from agent_platform.core.platforms.openai.parameters import OpenAIPlatformParameters

    defaults = {
        "name": "Test Agent",
        "description": "Test Description",
        "user_id": "test_user",
        "version": "1.0.0",
        "runbook_structured": Runbook(raw_text="# Test Runbook", content=[]),
        "platform_configs": [
            OpenAIPlatformParameters(
                name="test-openai",
                openai_api_key=SecretString("test-key"),
            )
        ],
        "agent_architecture": AgentArchitecture(
            name="agent_platform.architectures.default",
            version="1.0.0",
        ),
        "action_packages": [],
        "mcp_servers": [],
        "selected_tools": SelectedTools(),
        "question_groups": [],
        "mode": "conversational",
        "extra": {},
    }
    defaults.update(overrides)
    return Agent(**defaults)


def create_action_package_with_metadata(name: str, organization: str, version: str) -> dict[str, bytes]:
    """Create action package files with metadata."""
    metadata = {
        "metadata": {
            "name": name,
            "description": f"Test {name} package",
            "action_package_version": version,
        },
        "openapi.json": {
            "openapi": "3.1.0",
            "info": {"title": "Action Server", "version": "1.0.0"},
            "paths": {},
        },
    }

    return {
        AgentPackageConfig.action_package_metadata_filename: json.dumps(metadata).encode("utf-8"),
        "package.yaml": f"name: {name}\nversion: {version}".encode(),
        "actions.py": b"# Test actions",
    }


@pytest.mark.asyncio
async def test_build_agent_package_basic():
    """Test building an agent package from an agent project."""
    # Create an action package
    action_package = ActionPackage(
        name="test-package",
        organization="Test.Org",
        version="1.0.0",
    )

    # Create an agent with the action package
    agent = create_minimal_agent(action_packages=[action_package])

    # Create action package files
    action_package_files = create_action_package_with_metadata("test-package", "Test.Org", "1.0.0")

    # Create an agent project zip with action package as folder
    action_packages_map = {"Test.Org/test-package": action_package_files}
    project_zip_stream = await create_agent_project_zip(
        agent, semantic_data_models=[], action_packages_map=action_packages_map
    )
    project_zip_bytes = await collect_async_generator(project_zip_stream)

    # Build the agent package
    agent_package_bytes = await build_agent_package_from_project_zip(project_zip_bytes)

    # Verify the result is a valid zip
    assert agent_package_bytes is not None
    assert len(agent_package_bytes) > 0

    # Read and verify the agent package
    with zipfile.ZipFile(BytesIO(agent_package_bytes), "r") as agent_package_zip:
        # Check that agent-spec.yaml exists
        assert AgentPackageConfig.agent_spec_filename in agent_package_zip.namelist()

        # Check that metadata exists
        assert AgentPackageConfig.metadata_filename in agent_package_zip.namelist()

        # Check that action package is now a zip file
        expected_action_package_path = f"{AgentPackageConfig.actions_dirname}/Test.Org/test-package/1.0.0.zip"
        assert expected_action_package_path in agent_package_zip.namelist()

        # Verify the spec was updated to use "zip" type
        spec_raw = agent_package_zip.read(AgentPackageConfig.agent_spec_filename)
        agent_spec = AgentPackageSpec.from_yaml(spec_raw)
        spec_agent = agent_spec.agent_package.agents[0]

        assert len(spec_agent.action_packages) == 1
        assert spec_agent.action_packages[0].type == "zip"
        assert spec_agent.action_packages[0].path == "Test.Org/test-package/1.0.0.zip"

        # Verify metadata was generated
        metadata_raw = agent_package_zip.read(AgentPackageConfig.metadata_filename)
        metadata_list = json.loads(metadata_raw.decode())
        assert len(metadata_list) == 1
        metadata = metadata_list[0]
        assert metadata["name"] == "Test Agent"
        assert metadata["version"] == "1.0.0"
        assert len(metadata["action_packages"]) == 1


@pytest.mark.asyncio
async def test_build_agent_package_multiple_action_packages():
    """Test building an agent package with multiple action packages."""
    # Create multiple action packages
    action_packages = [
        ActionPackage(name="browsing", organization="Sema4.ai", version="1.3.3"),
        ActionPackage(name="email", organization="Sema4.ai", version="2.0.0"),
    ]

    agent = create_minimal_agent(action_packages=action_packages)

    # Create action package files
    action_packages_map = {
        "Sema4.ai/browsing": create_action_package_with_metadata("browsing", "Sema4.ai", "1.3.3"),
        "Sema4.ai/email": create_action_package_with_metadata("email", "Sema4.ai", "2.0.0"),
    }

    # Create agent project zip
    project_zip_stream = await create_agent_project_zip(
        agent, semantic_data_models=[], action_packages_map=action_packages_map
    )
    project_zip_bytes = await collect_async_generator(project_zip_stream)

    # Build the agent package
    agent_package_bytes = await build_agent_package_from_project_zip(project_zip_bytes)

    # Verify both action packages are included as zips
    with zipfile.ZipFile(BytesIO(agent_package_bytes), "r") as agent_package_zip:
        expected_paths = [
            f"{AgentPackageConfig.actions_dirname}/Sema4.ai/browsing/1.3.3.zip",
            f"{AgentPackageConfig.actions_dirname}/Sema4.ai/email/2.0.0.zip",
        ]

        for expected_path in expected_paths:
            assert expected_path in agent_package_zip.namelist()

        # Verify spec has both action packages with zip type
        spec_raw = agent_package_zip.read(AgentPackageConfig.agent_spec_filename)
        agent_spec = AgentPackageSpec.from_yaml(spec_raw)
        spec_agent = agent_spec.agent_package.agents[0]

        assert len(spec_agent.action_packages) == 2
        for ap in spec_agent.action_packages:
            assert ap.type == "zip"
            assert ap.path is not None
            assert ap.path.endswith(".zip") is True


@pytest.mark.asyncio
async def test_build_agent_package_invalid_zip():
    """Test that invalid zip raises error."""
    from agent_platform.core.errors import PlatformHTTPError

    with pytest.raises(PlatformHTTPError) as exc_info:
        await build_agent_package_from_project_zip(b"not a valid zip file")

    assert "not a valid ZIP file" in str(exc_info.value)


@pytest.mark.asyncio
async def test_build_agent_package_missing_metadata():
    """Test that action package without metadata raises error."""
    from agent_platform.core.errors import PlatformHTTPError

    # Create an action package
    action_package = ActionPackage(
        name="test-package",
        organization="Test.Org",
        version="1.0.0",
    )

    agent = create_minimal_agent(action_packages=[action_package])

    # Create action package files WITHOUT metadata
    action_package_files = {
        "package.yaml": b"name: test-package\nversion: 1.0.0",
        "actions.py": b"# Test actions",
    }

    action_packages_map = {"Test.Org/test-package": action_package_files}

    # Create agent project zip
    project_zip_stream = await create_agent_project_zip(
        agent, semantic_data_models=[], action_packages_map=action_packages_map
    )
    project_zip_bytes = await collect_async_generator(project_zip_stream)

    # Build should fail
    with pytest.raises(PlatformHTTPError) as exc_info:
        await build_agent_package_from_project_zip(project_zip_bytes)

    assert "missing __action_server_metadata__.json" in str(exc_info.value)


@pytest.mark.asyncio
async def test_build_agent_package_preserves_runbook():
    """Test that runbook is preserved in the agent package."""
    action_package = ActionPackage(
        name="test-package",
        organization="Test.Org",
        version="1.0.0",
    )

    # Create agent with custom runbook
    agent = create_minimal_agent(
        action_packages=[action_package],
        runbook_structured=Runbook(raw_text="# Custom Runbook\n\nTest content", content=[]),
    )

    action_packages_map = {
        "Test.Org/test-package": create_action_package_with_metadata("test-package", "Test.Org", "1.0.0")
    }

    project_zip_stream = await create_agent_project_zip(
        agent, semantic_data_models=[], action_packages_map=action_packages_map
    )
    project_zip_bytes = await collect_async_generator(project_zip_stream)

    # Build the agent package
    agent_package_bytes = await build_agent_package_from_project_zip(project_zip_bytes)

    # Verify runbook is preserved
    with zipfile.ZipFile(BytesIO(agent_package_bytes), "r") as agent_package_zip:
        assert AgentPackageConfig.runbook_filename in agent_package_zip.namelist()
        runbook_content = agent_package_zip.read(AgentPackageConfig.runbook_filename).decode("utf-8")
        assert "Custom Runbook" in runbook_content
        assert "Test content" in runbook_content
