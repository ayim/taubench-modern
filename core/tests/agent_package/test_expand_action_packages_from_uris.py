"""Tests for expand_action_packages_from_uris function."""

import json
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from agent_platform.core.actions.action_package import ActionPackage
from agent_platform.core.agent import Agent
from agent_platform.core.agent.agent_architecture import AgentArchitecture
from agent_platform.core.agent_package.config import AgentPackageConfig
from agent_platform.core.agent_package.create import expand_action_packages_from_uris
from agent_platform.core.errors import PlatformHTTPError
from agent_platform.core.runbook.runbook import Runbook
from agent_platform.core.selected_tools import SelectedTools
from agent_platform.core.utils.secret_str import SecretString


def create_minimal_agent(**overrides: Any) -> Agent:
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


def create_action_package_with_metadata(name: str, version: str) -> dict[str, bytes]:
    """Create action package files with metadata.

    Note: organization is not stored in action package metadata,
    it's stored in the agent's action package definition.

    The metadata structure matches what ActionPackageMetadata.model_validate expects
    from agent_metadata.py - a flat structure with name, description, action_package_version.
    """
    metadata = {
        "name": name,
        "description": f"Test {name} package",
        "action_package_version": version,
        "actions": [],
        "secrets": {},
    }

    return {
        AgentPackageConfig.action_package_metadata_filename: json.dumps(metadata).encode("utf-8"),
        "package.yaml": f"name: {name}\nversion: {version}".encode(),
        "actions.py": b"# Test actions",
    }


def create_action_package_zip(files: dict[str, bytes]) -> bytes:
    """Create a zip file containing the given files."""
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for file_path, content in files.items():
            zip_file.writestr(file_path, content)
    return zip_buffer.getvalue()


class TestExpandActionPackagesFromUris:
    """Tests for expand_action_packages_from_uris function."""

    @pytest.mark.asyncio
    async def test_returns_empty_dict_when_no_uris_provided(self):
        """Test that function returns empty dict when URIs list is empty."""
        agent = create_minimal_agent()
        result = await expand_action_packages_from_uris(agent, [])
        assert result == {}

    @pytest.mark.asyncio
    async def test_expands_multiple_action_packages_from_uris(self, tmp_path: Path):
        """Test expanding multiple action packages from file:// URIs."""
        # Create multiple action packages in agent definition
        action_packages = [
            ActionPackage(name="browsing", organization="Sema4.ai", version="1.3.3"),
            ActionPackage(name="email", organization="Sema4.ai", version="2.0.0"),
        ]
        agent = create_minimal_agent(action_packages=action_packages)

        # Create action package zip files
        browsing_files = create_action_package_with_metadata("browsing", "1.3.3")
        browsing_zip_bytes = create_action_package_zip(browsing_files)
        browsing_path = tmp_path / "browsing.zip"
        browsing_path.write_bytes(browsing_zip_bytes)

        email_files = create_action_package_with_metadata("email", "2.0.0")
        email_zip_bytes = create_action_package_zip(email_files)
        email_path = tmp_path / "email.zip"
        email_path.write_bytes(email_zip_bytes)

        # Create file URIs (use as_uri() for cross-platform compatibility)
        uris = [browsing_path.as_uri(), email_path.as_uri()]

        # Expand the action packages from URIs
        result = await expand_action_packages_from_uris(agent, uris)

        # Verify results
        assert len(result) == 2
        assert "Sema4.ai/browsing" in result
        assert "Sema4.ai/email" in result
        assert result["Sema4.ai/browsing"]["package.yaml"] == browsing_files["package.yaml"]
        assert result["Sema4.ai/email"]["package.yaml"] == email_files["package.yaml"]

    @pytest.mark.asyncio
    async def test_raises_error_when_action_package_not_in_agent_definition(self, tmp_path: Path):
        """Test that providing an action package not defined in agent raises error."""
        # Agent expects a different action package
        action_package = ActionPackage(
            name="expected-package",
            organization="Sema4.ai",
            version="1.0.0",
        )
        agent = create_minimal_agent(action_packages=[action_package])

        # Create action package with different name
        ap_files = create_action_package_with_metadata("wrong-package", "1.0.0")
        ap_zip_bytes = create_action_package_zip(ap_files)

        # Write to temp file
        ap_zip_path = tmp_path / "wrong-package.zip"
        ap_zip_path.write_bytes(ap_zip_bytes)

        # Create file URI (use as_uri() for cross-platform compatibility)
        file_uri = ap_zip_path.as_uri()

        with pytest.raises(PlatformHTTPError) as exc_info:
            await expand_action_packages_from_uris(agent, [file_uri])

        error_msg = str(exc_info.value)
        assert "wrong-package" in error_msg
        assert "is not defined in the agent's action packages" in error_msg

    @pytest.mark.asyncio
    async def test_raises_error_when_required_action_packages_missing(self, tmp_path: Path):
        """Test that missing required action packages raise error."""
        # Agent expects two action packages
        action_packages = [
            ActionPackage(name="browsing", organization="Sema4.ai", version="1.3.3"),
            ActionPackage(name="email", organization="Sema4.ai", version="2.0.0"),
        ]
        agent = create_minimal_agent(action_packages=action_packages)

        # Only provide one action package
        browsing_files = create_action_package_with_metadata("browsing", "1.3.3")
        browsing_zip_bytes = create_action_package_zip(browsing_files)
        browsing_path = tmp_path / "browsing.zip"
        browsing_path.write_bytes(browsing_zip_bytes)

        file_uri = browsing_path.as_uri()

        with pytest.raises(PlatformHTTPError) as exc_info:
            await expand_action_packages_from_uris(agent, [file_uri])

        error_msg = str(exc_info.value)
        assert "Missing required action packages" in error_msg
        assert "email" in error_msg
