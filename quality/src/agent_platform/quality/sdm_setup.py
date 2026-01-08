from __future__ import annotations

import http
import os
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx
import structlog
import yaml

from agent_platform.quality.models import SDMConfig
from agent_platform.quality.postgres_container import (
    PostgresConnectionInfo,
    PostgresContainerManager,
)

if TYPE_CHECKING:
    from agent_platform.core.payloads.data_connection import PostgresDataConnectionConfiguration

SDM_FILE_NAME = "sdm.yml"
SCHEMA_FILE_NAME = "schema.sql"
SEED_FILE_NAME = "seed.sql"

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class SDMSetup:
    """Handles SDM materialization and thread attachment."""

    # TODO: Throughout this class, we should probably use actual types from core payloads
    # instead of dicts.

    def __init__(self, server_url: str, test_data_root: Path):
        self.server_url = server_url.rstrip("/")
        self.test_data_root = test_data_root
        self._container_manager: PostgresContainerManager | None = None
        # Cache imported SDMs keyed by source path and agent to avoid re-importing.
        # All SDMs are pre-warmed during agent setup before parallel test execution,
        # so no locking is required.
        self._import_cache: dict[tuple[str, str | None], str] = {}

    async def cleanup(self) -> None:
        """Clean up resources used for SDM setup."""
        if self._container_manager is not None:
            await self._container_manager.cleanup_all()

    async def setup_sdm_infrastructure(self, cfg: SDMConfig) -> None:
        """Setup infrastructure (containers, data connections) without importing SDM.

        Use this for preinstalled agents where clones will import their own SDMs.
        This method sets up postgres containers and data connections that will be
        reused when the SDM is later imported with specific agent IDs.

        Args:
            cfg: SDM configuration specifying kind and path.
        """
        sdm_folder = self._resolve_sdm_folder(cfg.sdm_path)
        semantic_model = self._load_sdm_yaml(sdm_folder)

        match cfg.kind:
            case "postgres":
                # Setup postgres infrastructure
                connection_names = self._collect_data_connection_names(semantic_model)
                if not connection_names:
                    raise ValueError(f"No data_connection_name entries found in {sdm_folder / SDM_FILE_NAME}")

                connection_description = cfg.description or "Quality SDM data connection"

                if self._has_local_sql_files(sdm_folder):
                    # Start testcontainer and get connection info
                    if self._container_manager is None:
                        self._container_manager = PostgresContainerManager()
                    connection_info = await self._container_manager.get_or_start(sdm_folder)
                    logger.info(
                        "sdm_setup.infrastructure_local_postgres",
                        sdm_path=cfg.sdm_path,
                        host=connection_info.host,
                        port=connection_info.port,
                        database=connection_info.database,
                    )
                    for connection_name in sorted(connection_names):
                        configuration = self._configuration_from_connection_info(connection_info)
                        await self._ensure_data_connection(
                            name=connection_name,
                            engine="postgres",
                            configuration=configuration,
                            description=connection_description,
                        )
                else:
                    # Remote postgres - setup data connections from config
                    config_path = sdm_folder / "config.yml"
                    config_data = self._load_config_yml(config_path)
                    if config_data["engine"] != "postgres":
                        raise ValueError(f"Unsupported engine in {config_path}: {config_data['engine']}")

                    connection_description = cfg.description or config_data["description"]
                    for connection_name in sorted(connection_names or {config_data["name"]}):
                        configuration = self._build_postgres_configuration(**config_data["configuration"])
                        await self._ensure_data_connection(
                            name=connection_name,
                            engine="postgres",
                            configuration=configuration,
                            description=connection_description,
                        )

            case "excel":
                # Excel SDMs don't need infrastructure setup; file upload happens per-thread
                pass

            case _:
                raise ValueError(f"Unsupported SDM kind: {cfg.kind}")

        logger.info(
            "sdm_setup.infrastructure_complete",
            sdm_path=cfg.sdm_path,
        )

    async def prewarm_sdm(self, cfg: SDMConfig, agent_id: str | None = None) -> str:
        """Pre-import SDM and setup infrastructure without attaching to a thread.

        This should be called during agent setup, before tests run in parallel.
        It imports the SDM to the server, starts any required postgres containers,
        and creates data connections.

        Args:
            cfg: SDM configuration specifying kind and path.
            agent_id: Optional agent ID to associate with the SDM.

        Returns:
            The semantic_data_model_id for later attachment to threads.
        """
        # Setup infrastructure (containers, data connections)
        await self.setup_sdm_infrastructure(cfg)

        # Import the semantic model and cache the ID
        sdm_folder = self._resolve_sdm_folder(cfg.sdm_path)
        semantic_model = self._load_sdm_yaml(sdm_folder)
        sdm_id = await self._import_sdm_uncached(
            semantic_model, agent_id=agent_id, source_key=str(sdm_folder.resolve())
        )

        logger.info(
            "sdm_setup.prewarm_complete",
            sdm_path=cfg.sdm_path,
            sdm_id=sdm_id,
            agent_id=agent_id,
        )

        return sdm_id

    def get_prewarmed_sdm_id(self, sdm_path: str, agent_id: str | None) -> str:
        """Get a pre-warmed SDM ID from the cache.

        Args:
            sdm_path: The SDM path as specified in the test case config.
            agent_id: The agent ID used during pre-warming.

        Returns:
            The cached semantic_data_model_id.

        Raises:
            KeyError: If the SDM was not pre-warmed.
        """
        sdm_folder = self._resolve_sdm_folder(sdm_path)
        cache_key = (str(sdm_folder.resolve()), agent_id)
        sdm_id = self._import_cache.get(cache_key)
        if sdm_id is None:
            raise KeyError(
                f"SDM not pre-warmed: sdm_path={sdm_path}, agent_id={agent_id}. "
                "Call prewarm_sdm() during agent setup before running tests."
            )
        return sdm_id

    async def attach_sdms_to_thread(
        self,
        thread_id: str,
        sdm_configs: list[SDMConfig],
        agent_id: str | None = None,
    ) -> None:
        """Attach pre-warmed SDMs to a thread and upload Excel files if needed.

        This should be called when a thread is created, after SDMs have been
        pre-warmed during agent setup.

        Args:
            thread_id: The conversation thread ID to attach SDMs to.
            sdm_configs: List of SDM configurations from the test case.
            agent_id: The agent ID used during pre-warming.

        Raises:
            KeyError: If any SDM was not pre-warmed.
        """
        if not sdm_configs:
            return

        # Get all pre-warmed SDM IDs (raises KeyError if not pre-warmed)
        sdm_ids = [self.get_prewarmed_sdm_id(cfg.sdm_path, agent_id) for cfg in sdm_configs]

        # Upload Excel files to thread (only for excel SDMs)
        for cfg in sdm_configs:
            if cfg.kind == "excel":
                sdm_folder = self._resolve_sdm_folder(cfg.sdm_path)
                await self._upload_excel_file(thread_id, sdm_folder)

        # Attach SDMs to the thread
        await self._attach_sdms_to_thread(thread_id, sdm_ids)

    async def _find_sdm_by_name(self, sdm_name: str) -> list[str]:
        """Find SDM IDs that match the given name (case-insensitive).

        Args:
            sdm_name: The name of the SDM to search for.

        Returns:
            List of SDM IDs with matching names (empty if none found).
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{self.server_url}/api/v2/semantic-data-models/")
            response.raise_for_status()
            all_sdms = response.json() or []

        matching_ids = []
        for sdm_info in all_sdms:
            sdm_model = sdm_info.get("semantic_data_model", {})
            existing_name = sdm_model.get("name", "")
            if existing_name.lower() == sdm_name.lower():
                sdm_id = sdm_info.get("semantic_data_model_id")
                if sdm_id:
                    matching_ids.append(sdm_id)

        return matching_ids

    async def _import_sdm_uncached(self, semantic_model: dict[str, Any], agent_id: str | None, source_key: str) -> str:
        """Import SDM and cache the result. Deletes existing SDMs with same name first.

        No locking - must be called during setup phase.
        """
        cache_key = (source_key, agent_id)

        # Check cache first (idempotent)
        cached = self._import_cache.get(cache_key)
        if cached:
            return cached

        # Check for existing SDMs with same name and delete them
        sdm_name = semantic_model.get("name")
        if sdm_name:
            existing_ids = await self._find_sdm_by_name(sdm_name)
            if existing_ids:
                logger.warning(
                    "sdm_setup.deleting_existing_sdms",
                    sdm_name=sdm_name,
                    count=len(existing_ids),
                    sdm_ids=existing_ids,
                )
                async with httpx.AsyncClient(timeout=30.0) as client:
                    for sdm_id in existing_ids:
                        try:
                            await client.delete(
                                f"{self.server_url}/api/v2/semantic-data-models/{sdm_id}",
                            )
                            logger.info("sdm_setup.deleted_existing_sdm", sdm_id=sdm_id)
                        except httpx.HTTPStatusError as e:
                            # Log but continue - 404 means already deleted
                            if e.response.status_code != http.HTTPStatus.NOT_FOUND:
                                logger.warning(
                                    "sdm_setup.delete_failed",
                                    sdm_id=sdm_id,
                                    status=e.response.status_code,
                                )

        payload: dict[str, Any] = {"semantic_model": semantic_model}
        if agent_id is not None:
            payload["agent_id"] = agent_id

        logger.info(
            "sdm_setup.importing_sdm",
            sdm_path=source_key,
            agent_id=agent_id,
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.server_url}/api/v2/semantic-data-models/import",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        semantic_data_model_id = data.get("semantic_data_model_id")
        if not semantic_data_model_id:
            raise ValueError("Import SDM response missing semantic_data_model_id")

        self._import_cache[cache_key] = semantic_data_model_id

        return semantic_data_model_id

    async def _upload_excel_file(self, thread_id: str, sdm_folder: Path) -> None:
        # TODO: Do we want to support CSVs and multiple excel files?
        excel_files = list(sdm_folder.glob("*.xlsx"))
        if not excel_files:
            raise ValueError(f"No Excel file found in SDM folder: {sdm_folder}")

        excel_file = excel_files[0]

        async with httpx.AsyncClient(timeout=30.0) as client:
            with excel_file.open("rb") as file_handle:
                response = await client.post(
                    f"{self.server_url}/api/v2/threads/{thread_id}/files",
                    files=[
                        (
                            "files",
                            (
                                excel_file.name,
                                file_handle,
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            ),
                        )
                    ],
                )
                response.raise_for_status()

    async def _attach_sdms_to_thread(self, thread_id: str, sdm_ids: list[str]) -> None:
        unique_ids: list[str] = []
        seen = set()
        for sdm_id in sdm_ids:
            if sdm_id not in seen:
                unique_ids.append(sdm_id)
                seen.add(sdm_id)

        if not unique_ids:
            return

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.put(
                f"{self.server_url}/api/v2/threads/{thread_id}/semantic-data-models",
                json={"semantic_data_model_ids": unique_ids},
            )
            response.raise_for_status()

    async def _ensure_data_connection(
        self,
        name: str,
        engine: str,
        configuration: PostgresDataConnectionConfiguration,
        description: str,
    ) -> str:  # TODO: Do we want to return the DataConnection object instead?
        # TODO: Expand for all other engines with match-case block.
        from agent_platform.core.payloads.data_connection import (
            PostgresDataConnection,
            PostgresDataConnectionConfiguration,
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{self.server_url}/api/v2/data-connections/")
            response.raise_for_status()
            existing_connections = response.json() or []

        desired_config = asdict(configuration)
        desired_config["sslmode"] = (
            desired_config["sslmode"].value
            if hasattr(desired_config.get("sslmode"), "value")
            else desired_config.get("sslmode")
        )

        # Collect all matching connections - we'll delete stale ones and reuse exact matches
        matching_connection_id: str | None = None
        stale_connection_ids: list[str] = []

        if not isinstance(existing_connections, list):
            raise ValueError(f"Expected list of data connections, got {type(existing_connections)}")

        for connection in existing_connections:
            connection_name = connection.get("name")
            if not connection_name or connection_name.lower() != name.lower():
                continue

            if (connection.get("engine") or "").lower() != engine.lower():
                continue

            connection_id = connection.get("id") or connection.get("data_connection_id")
            if not connection_id:
                continue

            existing_config = dict(connection.get("configuration") or {})
            # Normalize possible float ports to int for comparison
            try:
                if "port" in existing_config:
                    existing_config["port"] = int(existing_config["port"])
            except (TypeError, ValueError):
                pass

            if existing_config == desired_config:
                # Exact match - we can reuse this one (but only keep first match)
                if matching_connection_id is None:
                    matching_connection_id = str(connection_id)
                else:
                    # Duplicate exact match - mark for deletion
                    stale_connection_ids.append(str(connection_id))
            else:
                # Stale config (e.g., old port/host) - mark for deletion
                stale_connection_ids.append(str(connection_id))

        # Delete ALL stale/duplicate connections
        if stale_connection_ids:
            logger.info(
                "sdm_setup.deleting_stale_connections",
                name=name,
                connection_ids=stale_connection_ids,
                desired_config=desired_config,
            )
            async with httpx.AsyncClient(timeout=30.0) as client:
                for stale_id in stale_connection_ids:
                    try:
                        await client.delete(f"{self.server_url}/api/v2/data-connections/{stale_id}")
                    except httpx.HTTPStatusError as e:
                        # Ignore 404 - connection may already be deleted
                        if e.response.status_code != http.HTTPStatus.NOT_FOUND:
                            raise

        # If we found an exact match, return it
        if matching_connection_id:
            logger.info(
                "sdm_setup.reusing_connection",
                name=name,
                connection_id=matching_connection_id,
            )
            return matching_connection_id

        config_payload = asdict(configuration)
        ssl_value = config_payload.get("sslmode")
        if isinstance(ssl_value, Enum):
            config_payload["sslmode"] = ssl_value.value

        payload = {
            "name": name,
            "description": description,
            "engine": engine,
            "configuration": config_payload,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.server_url}/api/v2/data-connections/",
                json=payload,
            )
            response.raise_for_status()
            created = response.json() or {}

        created_config = created.get("configuration") or {}
        if created_config:
            created["configuration"] = PostgresDataConnectionConfiguration(**created_config)
        created_connection = PostgresDataConnection(**created)

        if not created_connection.id:
            raise ValueError(f"Created data connection has no ID: {created}")

        return created_connection.id

    def _load_sdm_yaml(self, sdm_folder: Path) -> dict[str, Any]:
        sdm_file = sdm_folder / SDM_FILE_NAME
        if not sdm_file.exists():
            raise ValueError(f"{SDM_FILE_NAME} not found in {sdm_folder}")

        with sdm_file.open(encoding="utf-8") as handle:
            semantic_model = yaml.safe_load(handle) or {}

        if not isinstance(semantic_model, dict):
            raise ValueError(f"{SDM_FILE_NAME} in {sdm_folder} must contain a mapping")

        return semantic_model

    def _interpolate_config_value(self, key: str, value: Any, connection_name: str) -> int | str:
        """Interpolate $ENV_VAR_NAME and ${ENV_VAR:-default} patterns in config values.

        Args:
            key: Configuration field name
            value: Configuration value (may contain $ENV_VAR_NAME or ${VAR:-default})
            connection_name: Data connection name (for error messages)

        Returns:
            Interpolated value with proper type conversion

        Raises:
            ValueError: If env var not found (when no default) or port conversion fails
        """
        # Interpolate environment variable patterns
        if isinstance(value, str) and value.startswith("$"):
            import re

            # Check for ${VAR:-default} syntax
            match = re.match(r"^\$\{([^:}]+):-([^}]*)\}$", value)
            if match:
                env_var_name = match.group(1)
                default_value = match.group(2)
                env_value = os.getenv(env_var_name, default_value)
            else:
                # Simple $VAR syntax (no default)
                env_var_name = value[1:].strip("{}")
                env_value = os.getenv(env_var_name)
                if env_value is None:
                    raise ValueError(
                        f"Environment variable '{env_var_name}' not set for field '{key}' "
                        f"in data connection '{connection_name}'"
                    )

            # Convert port to int if needed
            if key == "port":
                try:
                    return int(env_value)
                except ValueError as e:
                    raise ValueError(f"Invalid port value from env '{env_var_name}': {env_value}") from e
            return env_value

        # Handle literal values
        if key == "port":
            try:
                return int(value)
            except (ValueError, TypeError) as e:
                raise ValueError(f"Invalid port value: {value}") from e

        return value

    def _load_config_yml(self, config_path: Path) -> dict[str, Any]:
        if not config_path.exists():
            raise ValueError(f"config.yml not found at {config_path}")

        with config_path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}

        data_connection = data.get("data_connection") or {}
        if not isinstance(data_connection, dict):
            raise ValueError(f"Invalid config.yml at {config_path}: data_connection must be a mapping")
        engine_raw = data_connection.get("engine")
        engine = engine_raw.lower() if isinstance(engine_raw, str) else engine_raw
        name = data_connection.get("name")

        if not engine or not name:
            raise ValueError(f"Invalid config.yml at {config_path}: missing engine or name")

        # Interpolate $VAR patterns in config fields
        config_kwargs: dict[str, Any] = {}
        for key in ["host", "port", "database", "user", "password", "schema", "sslmode"]:
            value = data_connection.get(key)
            if value is not None:
                config_kwargs[key] = self._interpolate_config_value(key, value, name)

        config_kwargs.setdefault("schema", "public")
        required_keys = ["host", "port", "database", "user", "password"]
        missing_required = [field for field in required_keys if field not in config_kwargs]
        if missing_required:
            missing_str = ", ".join(missing_required)
            raise ValueError(f"Missing required data connection fields in config.yml: {missing_str}")

        return {
            "engine": engine,
            "name": name,
            "description": data_connection.get("description", "Quality SDM data connection"),
            "configuration": config_kwargs,
        }

    def _configuration_from_connection_info(
        self, connection_info: PostgresConnectionInfo
    ) -> PostgresDataConnectionConfiguration:
        return self._build_postgres_configuration(
            host=connection_info.host,
            port=connection_info.port,
            database=connection_info.database,
            user=connection_info.user,
            password=connection_info.password,
            schema=connection_info.schema,
            sslmode=connection_info.sslmode,
        )

    def _build_postgres_configuration(
        self,
        *,
        host: str,
        port: int | str,
        database: str,
        user: str,
        password: str,
        schema: str | None = "public",
        sslmode: str | None = None,
    ) -> PostgresDataConnectionConfiguration:
        from agent_platform.core.payloads.data_connection import (
            PostgresDataConnectionConfiguration,
            Sslmode,
        )

        port_value = int(port)
        sslmode_value = sslmode.lower() if isinstance(sslmode, str) else sslmode
        sslmode_enum = Sslmode(sslmode_value) if sslmode_value else None
        configuration = PostgresDataConnectionConfiguration(
            host=host,
            port=port_value,
            database=database,
            user=user,
            password=password,
            schema=schema or "public",
            sslmode=sslmode_enum,
        )
        return configuration

    def _resolve_sdm_folder(self, sdm_path: str) -> Path:
        sdm_folder = self.test_data_root / sdm_path
        if not sdm_folder.exists():
            raise ValueError(f"SDM folder not found: {sdm_folder}")

        return sdm_folder

    def _get_container_manager(self) -> PostgresContainerManager:
        """Get or create the postgres container manager.

        Note: This is called during agent setup (prewarm phase), not during
        parallel test execution, so no locking is required.
        """
        if self._container_manager is None:
            self._container_manager = PostgresContainerManager()
        return self._container_manager

    def _collect_data_connection_names(self, semantic_model: dict[str, Any]) -> set[str]:
        connection_names: set[str] = set()
        for table in semantic_model.get("tables", []):
            base_table = table.get("base_table") or {}
            name = base_table.get("data_connection_name")
            if name:
                connection_names.add(name)
        return connection_names

    def _has_local_sql_files(self, sdm_folder: Path) -> bool:
        return (sdm_folder / SCHEMA_FILE_NAME).exists() and (sdm_folder / SEED_FILE_NAME).exists()
