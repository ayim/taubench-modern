"""Action package metadata processing.

This module handles reading and generating metadata from action packages,
including datasource extraction and configuration.
Works with in-memory zip files via ActionPackageHandler.
"""

from __future__ import annotations

import os
from typing import Any

import structlog

from agent_platform.core.agent_package.config import AgentPackageConfig
from agent_platform.core.agent_package.handler.action_package import ActionPackageHandler
from agent_platform.core.agent_package.metadata.agent_metadata import (
    ActionPackageMetadata,
    ActionPackageMetadataAction,
    ActionSecretsConfig,
    AgentPackageActionPackageMetadata,
    AgentPackageDatasource,
    ExternalEndpoint,
)
from agent_platform.core.agent_package.spec import SpecActionPackage

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def get_datasource_name(datasource: dict[str, Any], engine: str) -> str:
    """Get the name of a datasource based on its engine.

    Different engines use different fields for the datasource name.

    Args:
        datasource: Datasource configuration dictionary.
        engine: The engine type.

    Returns:
        The datasource name.
    """
    if engine == "files":
        return datasource.get("created_table", "")
    elif engine == "prediction:lightwood":
        return datasource.get("model_name", "")
    else:
        return datasource.get("name", "")


def get_raw_datasources(raw_metadata: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract raw datasources from action package metadata.

    Args:
        raw_metadata: Raw metadata dictionary.

    Returns:
        List of datasource configuration dictionaries.
    """
    metadata = raw_metadata.get("metadata", {})
    data = metadata.get("data", {})
    datasources = data.get("datasources", [])
    return datasources if isinstance(datasources, list) else []


class ActionPackageMetadataReader:
    """Reads and processes action package metadata from agent packages.

    This class handles reading metadata from action packages (both nested zip files
    and folders within the package), collecting metadata from all packages in an
    agent spec, generating the final metadata structure, and extracting datasources.

    Works with in-memory zip files via ActionPackageHandler.

    Attributes:
        _handler: Package handler for reading files from the zip.
    """

    def __init__(self, handler: ActionPackageHandler) -> None:
        """Initialize the reader with an optional package handler.

        Args:
            handler: Package handler for reading files from the agent package.
                     Can be None if only using datasource extraction methods.
        """
        self._handler = handler

    async def get_agent_package_action_packages_metadata(
        self,
        raw_metadata: dict[str, Any],
        action_package_spec: SpecActionPackage,
    ) -> AgentPackageActionPackageMetadata:
        """Generate action package metadata from raw metadata.

        Processes the raw metadata from __action_server_metadata__.json and
        extracts actions from the OpenAPI spec.

        Args:
            raw_metadata: Raw metadata dictionary from the action package.
            action_package_spec: Action package specification from agent spec.

        Returns:
            AgentPackageActionPackageMetadata with processed data.
        """
        # Extract nested metadata
        nested_metadata = raw_metadata.get("metadata", {})

        # Extract external endpoints from metadata
        external_endpoints = self._extract_external_endpoints(nested_metadata)

        # Validate secrets from raw metadata to proper ActionSecretsConfig instances
        raw_secrets = nested_metadata.get("secrets", {})
        secrets = {k: ActionSecretsConfig.model_validate(v) for k, v in raw_secrets.items()}

        # Build base action package metadata
        action_pkg_metadata = ActionPackageMetadata(
            name=nested_metadata.get("name", ""),
            description=nested_metadata.get("description", ""),
            version=nested_metadata.get("action_package_version", ""),
            secrets=secrets,
            actions=[],
            external_endpoints=external_endpoints,
        )

        # Extract actions from OpenAPI spec
        actions = self._extract_actions_from_openapi(raw_metadata)

        # Load icon if it exists (requires handler)
        if self._handler is None:
            raise ValueError("Handler is required for action package metadata processing")
        icon = await self._handler.load_icon()

        # Normalize path to use forward slashes
        full_ap_path = action_package_spec.path or ""
        normalized_path = full_ap_path.replace("\\", "/")
        if action_package_spec.type == "folder":
            folder_path = normalized_path
        else:
            # Get the folder path from the full path
            folder_path = os.path.dirname(normalized_path)

        # Get action_package_version from metadata
        action_package_version = nested_metadata.get("action_package_version", "")

        return AgentPackageActionPackageMetadata(
            name=action_pkg_metadata.name,
            description=action_pkg_metadata.description,
            version=action_pkg_metadata.version,
            secrets=action_pkg_metadata.secrets,
            actions=actions,
            external_endpoints=action_pkg_metadata.external_endpoints,
            whitelist=action_package_spec.whitelist or "",
            icon=icon,
            path=folder_path,
            full_path=normalized_path,
            action_package_version=action_package_version,
        )

    def _extract_actions_from_openapi(
        self,
        raw_metadata: dict[str, Any],
    ) -> list[ActionPackageMetadataAction]:
        """Extract actions from the OpenAPI spec in raw metadata."""
        actions: list[ActionPackageMetadataAction] = []
        openapi_spec = raw_metadata.get("openapi.json", {})
        paths = openapi_spec.get("paths", {})

        for path_item in paths.values():
            post_op = path_item.get("post", {})
            if post_op:
                actions.append(
                    ActionPackageMetadataAction(
                        description=post_op.get("description", ""),
                        name=post_op.get("operationId", ""),
                        summary=post_op.get("summary", ""),
                        operation_kind=post_op.get("x-operation-kind", "action"),
                    )
                )

        return actions

    def _extract_external_endpoints(
        self,
        nested_metadata: dict[str, Any],
    ) -> list[ExternalEndpoint]:
        """Extract external endpoints from the metadata.

        Args:
            nested_metadata: The nested metadata dictionary from raw metadata.

        Returns:
            List of ExternalEndpoint objects.
        """
        raw_endpoints = nested_metadata.get("external-endpoints", [])
        if not raw_endpoints:
            return []

        endpoints: list[ExternalEndpoint] = []
        for ep_data in raw_endpoints:
            try:
                endpoint = ExternalEndpoint.model_validate(ep_data)
                endpoints.append(endpoint)
            except Exception as e:
                logger.warning(
                    "Failed to parse external endpoint",
                    endpoint_data=ep_data,
                    error=str(e),
                )

        return endpoints

    async def extract_datasources(
        self,
        action_package_path: str,
        raw_metadata: dict[str, Any],
    ) -> list[AgentPackageDatasource]:
        """Extract datasources from all action package metadatas.

        Handles deduplication and file path resolution for "files" engine.

        Args:
            raw_metadatas: Dictionary of action package path to raw metadata.

        Returns:
            List of AgentPackageDatasource instances.
        """
        name_engine_map: dict[str, str] = {}
        datasources: list[AgentPackageDatasource] = []

        self._process_datasources_from_action_package(action_package_path, raw_metadata, name_engine_map, datasources)

        return datasources

    def _process_datasources_from_action_package(
        self,
        action_package_path: str,
        raw_metadata: dict[str, Any],
        name_engine_map: dict[str, str],
        datasources: list[AgentPackageDatasource],
    ) -> None:
        """Process datasources from a single action package."""
        raw_datasources = get_raw_datasources(raw_metadata)

        for ds in raw_datasources:
            engine = ds.get("engine", "")
            name = get_datasource_name(ds, engine)

            if not self._check_datasource_duplicate(name, engine, name_engine_map):
                continue

            config = self._resolve_datasource_file_paths(ds, engine, action_package_path)

            datasource = AgentPackageDatasource(
                customer_facing_name=name,
                engine=engine,
                description=ds.get("description", ""),
                configuration=config,
            )
            datasources.append(datasource)
            name_engine_map[name] = engine

    def _check_datasource_duplicate(
        self,
        name: str,
        engine: str,
        name_engine_map: dict[str, str],
    ) -> bool:
        """Check if a datasource is a duplicate.

        Returns:
            True if the datasource should be processed, False if it's a duplicate.
        """
        stored_engine = name_engine_map.get(name)
        if stored_engine is None:
            return True

        if stored_engine == engine:
            logger.debug(
                "Skipping duplicate datasource",
                datasource_name=name,
                engine=engine,
            )
            return False

        return False

    def _resolve_datasource_file_paths(
        self,
        ds: dict[str, Any],
        engine: str,
        action_package_path: str,
    ) -> dict[str, Any]:
        """Resolve file paths for datasources with 'files' engine."""
        config = ds.copy()

        if engine != "files":
            return config

        file_path = ds.get("file", "")
        full_file_path = f"{AgentPackageConfig.actions_dirname}/{action_package_path}/{file_path}"

        # Update file path to be relative to agent project root
        config["file"] = full_file_path.replace("\\", "/")

        return config
