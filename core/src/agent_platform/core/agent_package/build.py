from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

import structlog

from agent_platform.core.agent_package.config import AgentPackageConfig
from agent_platform.core.agent_package.handler.action_package import ActionPackageContent, ActionPackageHandler
from agent_platform.core.agent_package.handler.agent_package import AgentPackageHandler
from agent_platform.core.agent_package.metadata.agent_metadata_generator import AgentMetadataGenerator
from agent_platform.core.agent_package.spec import SpecActionPackage
from agent_platform.core.agent_package.utils import create_action_package_path
from agent_platform.core.errors import ErrorCode, PlatformHTTPError

logger = structlog.get_logger(__name__)

if TYPE_CHECKING:
    from agent_platform.core.agent_package.handler.action_package import ActionPackageHandler
    from agent_platform.core.agent_package.spec import AgentPackageSpec, SpecActionPackageType, SpecAgent


class AgentPackageBuilder:
    """Builds an Agent Package from a zipped Agent Project.

    This class transforms an Agent Project (with action packages as folders)
    into an Agent Package (with action packages as zip files).

    Usage:
        async with AgentPackageBuilder(project_zip_bytes) as builder:
            agent_package_bytes = await builder.build()
    """

    def __init__(self, agent_project_handler: AgentPackageHandler) -> None:
        """Initialize the builder with the project zip bytes.

        Args:
            agent_project_handler: The handler for the agent project.
        """
        self._project_handler: AgentPackageHandler = agent_project_handler
        self._output_handler: AgentPackageHandler | None = None
        self._spec_agent: SpecAgent | None = None
        self._agent_package_spec: AgentPackageSpec | None = None
        self._action_package_handlers: list[tuple[str, ActionPackageHandler]] = []

    async def __aexit__(self, exc_type: type | None, exc_val: Exception | None, exc_tb: object) -> None:
        """Clean up all handlers."""
        logger.debug(
            "Cleaning up AgentPackageBuilder context",
            action_package_handlers_count=len(self._action_package_handlers),
            has_exception=exc_type is not None,
        )
        # Clean up action package handlers
        for _, handler in self._action_package_handlers:
            handler.close()
        self._action_package_handlers.clear()

        # Clean up output handler
        if self._output_handler:
            self._output_handler.close()
            self._output_handler = None

        # Clean up project handler
        if self._project_handler:
            self._project_handler.close()
        logger.debug("AgentPackageBuilder cleanup complete")

    async def build(self, action_package_type: SpecActionPackageType) -> AsyncGenerator[bytes, None]:
        """Build the agent package.

        The process:
        1. Read and validate the agent-spec.yaml from the project
        2. For each action package folder:
           - Verify it has __action_server_metadata__.json
           - Zip the folder contents or copy the folder contents based on action_package_type
           - Store as actions/<org>/<name>/<version>.zip or actions/<org>/<name>/...
        3. Update the agent spec to use the selected type and new paths
        4. Generate agent package metadata
        5. Return the final agent package zip

        Returns:
            The Agent Package zip file bytes.

        Raises:
            PlatformHTTPError: If the project is invalid or action packages are missing metadata.
        """
        if not self._project_handler:
            raise RuntimeError("Builder must be used as async context manager")

        # Create output handler for the new package
        self._output_handler = AgentPackageHandler.create_empty()

        # Read spec from the project
        self._agent_package_spec = await self._project_handler.read_agent_spec()

        # Get the spec agent from the project
        self._spec_agent = await self._project_handler.get_spec_agent()

        # Update the spec with new action package paths
        self._spec_agent.action_packages = await self._process_action_packages(action_package_type)

        # Write the updated agent-spec.yaml
        await self._output_handler.write_agent_spec(self._agent_package_spec)

        # Copy other files from the project
        await self._copy_project_files_to_output()

        # Flush the writer so the zip file is readable for metadata generation
        self._output_handler.flush_writer()

        # Generate and write metadata
        metadata = await AgentMetadataGenerator.generate_from_handler(self._output_handler)
        await self._output_handler.write_metadata(metadata)

        return self._output_handler.to_stream()

    async def _collect_action_package_files(
        self,
        action_package: SpecActionPackage,
    ) -> ActionPackageContent:
        """Collect all files for an action package from the project.

        Args:
            action_package: The action package spec entry.

        Returns:
            Dictionary mapping relative file paths to file content bytes.

        Raises:
            PlatformHTTPError: If required metadata is missing.
        """
        if not self._project_handler:
            raise RuntimeError("Builder must be used as async context manager")

        if not action_package.path:
            logger.warning("Action package missing path in spec", action_package_name=action_package.name)
            raise PlatformHTTPError(
                error_code=ErrorCode.UNPROCESSABLE_ENTITY,
                message=f"Action package '{action_package.name}' is missing path in spec",
            )

        # The path in the project is: actions/<path>
        action_package_folder_prefix = f"{AgentPackageConfig.actions_dirname}/{action_package.path}/"
        logger.debug("Collecting files for action package", path_prefix=action_package_folder_prefix)

        # Get all files from the project
        all_files = await self._project_handler.list_files()

        # Collect all files for this action package
        action_package_files: ActionPackageContent = {}
        found_metadata = False

        for filename in all_files:
            if filename.startswith(action_package_folder_prefix):
                # Get the relative path within the action package
                relative_path = filename[len(action_package_folder_prefix) :]

                # Skip empty paths (directories) and the parent folder itself
                if not relative_path or filename.endswith("/"):
                    continue

                # Check if this is the metadata file
                if relative_path == AgentPackageConfig.action_package_metadata_filename:
                    found_metadata = True

                # Read the file content
                action_package_files[relative_path] = await self._project_handler.read_file(filename)

        # Verify metadata file exists
        if not found_metadata:
            metadata_filename = AgentPackageConfig.action_package_metadata_filename
            logger.warning(
                "Action package missing metadata file",
                action_package_path=action_package.path,
                expected_file=metadata_filename,
            )
            raise PlatformHTTPError(
                error_code=ErrorCode.UNPROCESSABLE_ENTITY,
                message=f"Action package '{action_package.path}' is missing {metadata_filename}",
            )

        logger.debug(
            "Collected action package files",
            action_package_path=action_package.path,
            file_count=len(action_package_files),
        )
        return action_package_files

    async def _process_action_packages(self, action_package_type: SpecActionPackageType) -> list[SpecActionPackage]:
        """Process all action packages: collect files, zip them, and add to output.

        Returns:
            List of updated action package spec entries with updated paths.

        Raises:
            PlatformHTTPError: If action packages are invalid.
        """
        if not self._spec_agent or not self._output_handler:
            raise RuntimeError("Builder must be used as async context manager")

        updated_action_packages: list[SpecActionPackage] = []
        logger.debug("Processing action packages", count=len(self._spec_agent.action_packages))

        for action_package in self._spec_agent.action_packages:
            logger.debug(
                "Processing action package",
                name=action_package.name,
                organization=action_package.organization,
                version=action_package.version,
            )

            # Collect all files for this action package
            action_package_files = await self._collect_action_package_files(action_package)

            if action_package_type == "zip":
                # Create handler with zipped action package files
                ap_handler = await ActionPackageHandler.create_empty().write_package_contents(action_package_files)

                # Get the zip bytes for writing to output
                action_package_zip_bytes = ap_handler.to_zip_bytes()

                # Create the new zip path: <org>/<name>/<version>.zip
                action_package_path = create_action_package_path(
                    "zip", action_package.organization, action_package.name, action_package.version
                )

                # Write to output using handler
                await self._output_handler.write_file(
                    f"{AgentPackageConfig.actions_dirname}/{action_package_path}",
                    action_package_zip_bytes,
                )

                # Keep the handler for cleanup (tracked by instance)
                self._action_package_handlers.append((action_package_path, ap_handler))

                logger.debug(
                    "Action package zipped and written",
                    path=action_package_path,
                    file_count=len(action_package_files),
                    zip_size_bytes=len(action_package_zip_bytes),
                )
            elif action_package_type == "folder":
                # Create the new folder path: <org>/<name>
                action_package_path = create_action_package_path(
                    "folder", action_package.organization, action_package.name, action_package.version
                )
                await self._output_handler.write_action_package(action_package_path, action_package_files)

                logger.debug(
                    "Action package folder written",
                    path=action_package_path,
                    file_count=len(action_package_files),
                )
            else:
                raise ValueError(f"Invalid action package type: {action_package_type}")

            # Create updated action package spec entry
            updated_action_package = SpecActionPackage(
                name=action_package.name,
                organization=action_package.organization,
                version=action_package.version,
                type=action_package_type,
                whitelist=action_package.whitelist,
                path=action_package_path,
            )
            updated_action_packages.append(updated_action_package)

        logger.debug("All action packages processed", count=len(updated_action_packages))
        return updated_action_packages

    async def _copy_project_files_to_output(self) -> None:
        """Copy non-action-package files from project to output.

        This includes files like runbook, conversation guide, etc., but excludes:
        - agent-spec.yaml (will be written separately with updates)
        - actions/ directory (already processed)
        - directories (empty entries)
        """
        from sema4ai.common.package_exclude import PackageExcludeHandler

        if not self._project_handler or not self._output_handler:
            raise RuntimeError("Builder must be used as async context manager")

        all_files = await self._project_handler.list_files()
        logger.debug("Copying project files to output", total_files_in_project=len(all_files))

        exclude_rules = self._agent_package_spec.agent_package.exclude if self._agent_package_spec else []
        exclude_rules_list = exclude_rules if exclude_rules is not None else []

        logger.debug("Applying exclude rules", exclude_rules=exclude_rules_list)

        exclude_handler = PackageExcludeHandler()
        exclude_handler.fill_exclude_patterns(exclude_rules_list)

        candidate_files: list[str] = []
        for filename in all_files:
            # Skip directories
            if filename.endswith("/"):
                continue
            # Skip agent-spec.yaml (we write the updated version separately)
            if filename == AgentPackageConfig.agent_spec_filename:
                continue
            # Skip action packages folder (already processed)
            if filename.startswith(f"{AgentPackageConfig.actions_dirname}/"):
                continue
            candidate_files.append(filename)

        logger.debug("Filtering project files", candidate_files=candidate_files)

        accepted_files = exclude_handler.filter_relative_paths_excluding_patterns(candidate_files)
        logger.debug("Project files after filtering", accepted_files=accepted_files)

        files_included_in_agent_project_count = 0
        for filename in accepted_files:
            # Copy the file
            file_content = await self._project_handler.read_file(filename)
            await self._output_handler.write_file(filename, file_content)
            files_included_in_agent_project_count += 1

        logger.debug("Project files copied to output", total_files_included=files_included_in_agent_project_count)
