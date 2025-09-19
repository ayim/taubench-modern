"""Tests for the lifespan function to detect asyncio issues."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from pyleak import no_event_loop_blocking, no_task_leaks

from agent_platform.server.lifespan import create_combined_lifespan, lifespan


class TestLifespan:
    """Test the lifespan function for asyncio issues."""

    def _create_mock_app(self):
        """Create a mock FastAPI app."""
        return FastAPI()

    def _setup_basic_mocks(self):
        """Set up basic mocks that are common across all tests."""
        # Create storage instance mock
        storage_instance = MagicMock()
        storage_instance.setup = AsyncMock()
        storage_instance.teardown = AsyncMock()

        # Create quotas service mock
        quotas_service = AsyncMock()

        return storage_instance, quotas_service

    def _mock_lifespan_dependencies(self, enable_workers=False):
        """Create a context manager that mocks all lifespan dependencies."""
        storage_instance, quotas_service = self._setup_basic_mocks()

        # We do not mock ShutdownManager or background workers because we want to test the
        # graceful shutdown process in lifespan.
        patches = [
            patch.multiple(
                "agent_platform.server.lifespan",
                llms_metadata_loader=MagicMock(
                    load_data=MagicMock(return_value=None), model_count=10
                ),
                SecretService=MagicMock(
                    get_instance=MagicMock(return_value=MagicMock(setup=MagicMock()))
                ),
                start_data_retention_worker=MagicMock(return_value=MagicMock(cancel=MagicMock())),
                ResponseStreamPipe=MagicMock(_DIFF_POOL=MagicMock(shutdown=MagicMock())),
                SystemConfig=MagicMock(
                    enable_workitems=enable_workers, enable_evals=enable_workers
                ),
                SystemPaths=MagicMock(upload_dir=MagicMock()),
                run_automatic_migration=AsyncMock(return_value=True),
            ),
            patch(
                "agent_platform.server.lifespan.StorageService",
                MagicMock(get_instance=MagicMock(return_value=storage_instance)),
            ),
            patch(
                "agent_platform.server.lifespan.QuotasService",
                MagicMock(get_instance=quotas_service),
            ),
        ]

        # Return a context manager that applies all patches
        from contextlib import ExitStack

        stack = ExitStack()
        for patch_obj in patches:
            stack.enter_context(patch_obj)
        return stack

    @pytest.mark.asyncio
    async def test_lifespan_no_event_loop_blocking(self):
        """Test that lifespan function doesn't block the event loop."""
        async with no_event_loop_blocking(threshold=0.1):
            with self._mock_lifespan_dependencies(enable_workers=False):
                app = self._create_mock_app()
                async with lifespan(app):
                    await asyncio.sleep(0.01)

    @pytest.mark.asyncio
    async def test_lifespan_no_task_leaks(self):
        """Test that lifespan function doesn't leak asyncio tasks."""
        async with no_task_leaks():
            with self._mock_lifespan_dependencies(enable_workers=False):
                app = self._create_mock_app()
                async with lifespan(app):
                    await asyncio.sleep(0.01)

    @pytest.mark.asyncio
    async def test_lifespan_with_background_workers_no_leaks(self):
        """Test lifespan with background workers enabled doesn't leak tasks."""
        async with no_task_leaks():
            with self._mock_lifespan_dependencies(enable_workers=True):
                app = self._create_mock_app()
                async with lifespan(app):
                    await asyncio.sleep(0.01)

    @pytest.mark.asyncio
    async def test_combined_lifespan_no_leaks(self):
        """Test that create_combined_lifespan doesn't leak tasks."""
        async with no_task_leaks():
            with self._mock_lifespan_dependencies(enable_workers=False):
                # Create mock MCP app
                mock_mcp_app = MagicMock()
                mock_mcp_app.router = MagicMock()
                mock_mcp_app.router.lifespan_context.return_value.__aenter__ = AsyncMock()
                mock_mcp_app.router.lifespan_context.return_value.__aexit__ = AsyncMock()

                app = self._create_mock_app()
                combined_lifespan = create_combined_lifespan(mock_mcp_app)
                async with combined_lifespan(app):
                    await asyncio.sleep(0.01)

    @pytest.mark.asyncio
    async def test_lifespan_exception_handling_no_leaks(self):
        """Test that lifespan handles exceptions without leaking tasks."""
        async with no_task_leaks():
            with self._mock_lifespan_dependencies(enable_workers=False):
                # Override the llms_metadata_loader to simulate an exception
                with patch("agent_platform.server.lifespan.llms_metadata_loader") as mock_loader:
                    mock_loader.load_data.side_effect = Exception("Setup failed")
                    app = self._create_mock_app()
                    with pytest.raises(Exception, match="Setup failed"):
                        async with lifespan(app):
                            pass
