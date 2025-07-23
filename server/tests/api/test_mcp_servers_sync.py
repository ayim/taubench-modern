import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from agent_platform.core.mcp.mcp_server import MCPServer, MCPServerSource
from agent_platform.server.api.private_v2.mcp_servers import (
    _read_mcp_servers_config_file,
    _sync_file_based_mcp_servers,
)
from agent_platform.server.storage.base import BaseStorage

# Sample config data for testing
SAMPLE_CONFIG_DATA = {
    "mcpServers": {
        "NPX": {
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-memory"],
            "env": {},
        },
        "DeepWiki": {"transport": "auto", "url": "https://mcp.deepwiki.com/sse", "headers": {}},
        "My new MCP Server": {
            "transport": "sse",
            "url": "https://mcp.deepwiki.com/sse",
            "headers": {},
        },
    }
}

EMPTY_CONFIG_DATA = {"mcpServers": {}}

INVALID_CONFIG_DATA = {"wrongKey": {}}


class TestReadMcpServersConfigFile:
    """Test the _read_mcp_servers_config_file function."""

    def test_read_config_file_success(self):
        """Test successfully reading a valid config file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(SAMPLE_CONFIG_DATA, f)
            config_path = f.name

        with patch(
            "agent_platform.server.api.private_v2.mcp_servers.SEMA4AI_AGENT_SERVER_MCP_SERVERS_CONFIG_FILE",
            config_path,
        ):
            servers = _read_mcp_servers_config_file()

        # Clean up
        Path(config_path).unlink()

        assert len(servers) == 3

        # Verify NPX server
        npx_server = next(s for s in servers if s.name == "NPX")
        assert npx_server.transport == "stdio"
        assert npx_server.command == "npx"
        assert npx_server.args == ["-y", "@modelcontextprotocol/server-memory"]
        assert npx_server.env == {}

        # Verify DeepWiki server (auto transport should become sse due to URL)
        deepwiki_server = next(s for s in servers if s.name == "DeepWiki")
        assert deepwiki_server.transport == "sse"  # auto becomes sse due to URL
        assert deepwiki_server.url == "https://mcp.deepwiki.com/sse"

        # Verify My new MCP Server
        new_server = next(s for s in servers if s.name == "My new MCP Server")
        assert new_server.transport == "sse"
        assert new_server.url == "https://mcp.deepwiki.com/sse"

    def test_read_config_file_not_found(self):
        """Test behavior when config file doesn't exist."""
        with patch(
            "agent_platform.server.api.private_v2.mcp_servers.SEMA4AI_AGENT_SERVER_MCP_SERVERS_CONFIG_FILE",
            "/nonexistent/path.json",
        ):
            servers = _read_mcp_servers_config_file()

        assert servers == []

    def test_read_config_file_no_env_var(self):
        """Test behavior when environment variable is not set."""
        with patch(
            "agent_platform.server.api.private_v2.mcp_servers.SEMA4AI_AGENT_SERVER_MCP_SERVERS_CONFIG_FILE",
            None,
        ):
            servers = _read_mcp_servers_config_file()

        assert servers == []

    def test_read_config_file_empty_env_var(self):
        """Test behavior when environment variable is empty string."""
        with patch(
            "agent_platform.server.api.private_v2.mcp_servers.SEMA4AI_AGENT_SERVER_MCP_SERVERS_CONFIG_FILE",
            "",
        ):
            servers = _read_mcp_servers_config_file()

        assert servers == []

    def test_read_config_file_invalid_json(self):
        """Test behavior with invalid JSON file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("invalid json content")
            config_path = f.name

        with patch(
            "agent_platform.server.api.private_v2.mcp_servers.SEMA4AI_AGENT_SERVER_MCP_SERVERS_CONFIG_FILE",
            config_path,
        ):
            servers = _read_mcp_servers_config_file()

        # Clean up
        Path(config_path).unlink()

        assert servers == []

    def test_read_config_file_empty_config(self):
        """Test reading an empty config file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(EMPTY_CONFIG_DATA, f)
            config_path = f.name

        with patch(
            "agent_platform.server.api.private_v2.mcp_servers.SEMA4AI_AGENT_SERVER_MCP_SERVERS_CONFIG_FILE",
            config_path,
        ):
            servers = _read_mcp_servers_config_file()

        # Clean up
        Path(config_path).unlink()

        assert servers == []

    def test_read_config_file_invalid_structure(self):
        """Test reading a config file with invalid structure."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(INVALID_CONFIG_DATA, f)
            config_path = f.name

        with patch(
            "agent_platform.server.api.private_v2.mcp_servers.SEMA4AI_AGENT_SERVER_MCP_SERVERS_CONFIG_FILE",
            config_path,
        ):
            servers = _read_mcp_servers_config_file()

        # Clean up
        Path(config_path).unlink()

        assert servers == []

    def test_read_config_file_invalid_server_config(self):
        """Test reading a config file with invalid server configuration."""
        invalid_server_config = {
            "mcpServers": {
                "ValidServer": {
                    "transport": "stdio",
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-memory"],
                },
                "InvalidServer": {
                    "transport": "invalid_transport",  # Invalid transport
                    "command": "test",
                },
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(invalid_server_config, f)
            config_path = f.name

        with patch(
            "agent_platform.server.api.private_v2.mcp_servers.SEMA4AI_AGENT_SERVER_MCP_SERVERS_CONFIG_FILE",
            config_path,
        ):
            servers = _read_mcp_servers_config_file()

        # Clean up
        Path(config_path).unlink()

        # Should return only the valid server, invalid one should be skipped
        assert len(servers) == 1
        assert servers[0].name == "ValidServer"


class TestSyncFileBasedMcpServers:
    """Test the _sync_file_based_mcp_servers function."""

    @pytest.fixture
    def mock_storage(self):
        """Create a mock storage object."""
        storage = AsyncMock(spec=BaseStorage)
        return storage

    @pytest.mark.asyncio
    async def test_sync_with_empty_config(self, mock_storage):
        """Test sync behavior when config file is empty."""
        mock_storage.list_mcp_servers_by_source.return_value = {
            "existing-file-server": "server-id-1"
        }

        with patch(
            "agent_platform.server.api.private_v2.mcp_servers._read_mcp_servers_config_file",
            return_value=[],
        ):
            await _sync_file_based_mcp_servers(mock_storage)

        # Should remove existing FILE servers
        mock_storage.delete_mcp_server.assert_called_once_with(["server-id-1"])

    @pytest.mark.asyncio
    async def test_sync_with_new_servers(self, mock_storage):
        """Test sync behavior when adding new servers from config."""
        # Mock that no FILE servers exist
        mock_storage.list_mcp_servers_by_source.return_value = {}
        mock_storage.get_mcp_server_by_name.return_value = None

        new_server = MCPServer(
            name="NPX",
            transport="stdio",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-memory"],
        )

        with patch(
            "agent_platform.server.api.private_v2.mcp_servers._read_mcp_servers_config_file",
            return_value=[new_server],
        ):
            await _sync_file_based_mcp_servers(mock_storage)

        # Should create the new server
        mock_storage.create_mcp_server.assert_called_once_with(new_server, MCPServerSource.FILE)

    @pytest.mark.asyncio
    async def test_sync_with_existing_server_update(self, mock_storage):
        """Test sync behavior when updating existing servers."""
        mock_storage.list_mcp_servers_by_source.return_value = {}

        existing_server = MCPServer(name="NPX", transport="stdio", command="old-command")
        mock_storage.get_mcp_server_by_name.return_value = (
            "server-id-1",
            existing_server,
            MCPServerSource.API,
        )

        updated_server = MCPServer(
            name="NPX",
            transport="stdio",
            command="npx",
            args=["-y", "@modelcontextprotocol/server-memory"],
        )

        with patch(
            "agent_platform.server.api.private_v2.mcp_servers._read_mcp_servers_config_file",
            return_value=[updated_server],
        ):
            await _sync_file_based_mcp_servers(mock_storage)

        # Should update the existing server and change source to FILE
        mock_storage.update_mcp_server.assert_called_once_with(
            "server-id-1", updated_server, MCPServerSource.FILE
        )

    @pytest.mark.asyncio
    async def test_sync_removes_obsolete_file_servers(self, mock_storage):
        """Test that obsolete FILE servers are removed."""
        # Mock existing FILE servers
        mock_storage.list_mcp_servers_by_source.return_value = {
            "old-server": "server-id-1",
            "another-old-server": "server-id-2",
        }
        mock_storage.get_mcp_server_by_name.return_value = None

        new_server = MCPServer(name="new-server", transport="stdio", command="npx")

        with patch(
            "agent_platform.server.api.private_v2.mcp_servers._read_mcp_servers_config_file",
            return_value=[new_server],
        ):
            await _sync_file_based_mcp_servers(mock_storage)

        # Should remove both old servers in a single call
        mock_storage.delete_mcp_server.assert_called_once_with(["server-id-1", "server-id-2"])

        # Should create the new server
        mock_storage.create_mcp_server.assert_called_once_with(new_server, MCPServerSource.FILE)

    @pytest.mark.asyncio
    async def test_sync_mixed_operations(self, mock_storage):
        """Test sync with mixed operations: create, update, delete."""
        # Mock existing FILE servers
        mock_storage.list_mcp_servers_by_source.return_value = {
            "keep-and-update": "server-id-1",
            "remove-me": "server-id-2",
        }

        # Mock get_mcp_server_by_name responses
        def get_server_by_name_side_effect(name, source):
            if name == "keep-and-update":
                existing_server = MCPServer(
                    name="keep-and-update", transport="stdio", command="old"
                )
                return ("server-id-1", existing_server, MCPServerSource.FILE)
            elif name == "create-new":
                return None
            return None

        mock_storage.get_mcp_server_by_name.side_effect = get_server_by_name_side_effect

        servers_from_file = [
            MCPServer(name="keep-and-update", transport="stdio", command="updated"),
            MCPServer(name="create-new", transport="sse", url="https://example.com"),
        ]

        with patch(
            "agent_platform.server.api.private_v2.mcp_servers._read_mcp_servers_config_file",
            return_value=servers_from_file,
        ):
            await _sync_file_based_mcp_servers(mock_storage)

        # Should delete the removed server
        mock_storage.delete_mcp_server.assert_called_once_with(["server-id-2"])

        # Should update the existing server
        mock_storage.update_mcp_server.assert_called_once_with(
            "server-id-1", servers_from_file[0], MCPServerSource.FILE
        )

        # Should create the new server
        mock_storage.create_mcp_server.assert_called_once_with(
            servers_from_file[1], MCPServerSource.FILE
        )

    @pytest.mark.asyncio
    async def test_sync_handles_storage_errors_gracefully(self, mock_storage):
        """Test that sync handles storage errors gracefully."""
        mock_storage.list_mcp_servers_by_source.return_value = {}
        mock_storage.get_mcp_server_by_name.return_value = None
        mock_storage.create_mcp_server.side_effect = Exception("Storage error")

        new_server = MCPServer(name="test-server", transport="stdio", command="test")

        with patch(
            "agent_platform.server.api.private_v2.mcp_servers._read_mcp_servers_config_file",
            return_value=[new_server],
        ):
            # Should not raise exception, just log the error
            await _sync_file_based_mcp_servers(mock_storage)

        # Should attempt to create the server
        mock_storage.create_mcp_server.assert_called_once()
