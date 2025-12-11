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


class SDMSetup:
    """Handles SDM materialization and thread attachment."""

    # TODO: Throughout this class, we should probably use actual types from core payloads
    # instead of dicts.

    def __init__(self, server_url: str, test_data_root: Path):
        self.server_url = server_url.rstrip("/")
        self.test_data_root = test_data_root
        self._container_manager: PostgresContainerManager | None = None
        # Cache imported SDMs keyed by source path and agent to avoid re-importing.
        self._import_cache: dict[tuple[str, str | None], str] = {}
        self._log: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

    async def ensure_sdms_for_thread(
        self,
        thread_id: str,
        sdm_configs: list[SDMConfig],
        agent_id: str | None = None,
    ) -> None:
        """Set up all SDMs for a thread."""
        if not sdm_configs:
            return

        semantic_model_ids: list[str] = []
        for cfg in sdm_configs:
            match cfg.kind:
                case "excel":
                    sdm_id = await self._ensure_excel_sdm(thread_id, cfg, agent_id=agent_id)
                case "postgres":
                    sdm_id = await self._ensure_postgres_sdm(thread_id, cfg, agent_id=agent_id)
                case _:  # pragma: no cover - validated by type
                    raise ValueError(f"Unsupported SDM kind: {cfg.kind}")

            semantic_model_ids.append(sdm_id)

        await self._attach_sdms_to_thread(thread_id, semantic_model_ids)

    async def cleanup(self) -> None:
        """Clean up resources used for SDM setup."""
        if self._container_manager is not None:
            await self._container_manager.cleanup_all()

    async def _ensure_excel_sdm(
        self,
        thread_id: str,
        cfg: SDMConfig,
        agent_id: str | None,
    ) -> str:
        sdm_folder = self._resolve_sdm_folder(cfg.sdm_path)
        semantic_model = self._load_sdm_yaml(sdm_folder)

        sdm_id = await self._import_sdm(
            semantic_model, agent_id=agent_id, source_key=str(sdm_folder.resolve())
        )
        await self._upload_excel_file(thread_id, sdm_folder)

        return sdm_id

    async def _ensure_postgres_sdm(
        self,
        thread_id: str,
        cfg: SDMConfig,
        agent_id: str | None,
    ) -> str:
        sdm_folder = self._resolve_sdm_folder(cfg.sdm_path)
        semantic_model = self._load_sdm_yaml(sdm_folder)
        connection_names = self._collect_data_connection_names(semantic_model)
        if not connection_names:
            raise ValueError(
                f"No data_connection_name entries found in {sdm_folder / SDM_FILE_NAME}"
            )

        connection_description = cfg.description or "Quality SDM data connection"
        data_connection_payloads: list[tuple[str, PostgresDataConnectionConfiguration]] = []
        if self._has_local_sql_files(sdm_folder):
            # The local testcontainer case
            connection_info = await self._get_container_manager().get_or_start(sdm_folder)
            self._log.info(
                "sdm_setup.local_postgres_connection",
                thread_id=thread_id,
                sdm_folder=str(sdm_folder),
                host=connection_info.host,
                port=connection_info.port,
                database=connection_info.database,
                user=connection_info.user,
            )
            for connection_name in sorted(connection_names):
                data_connection_payloads.append(
                    (connection_name, self._configuration_from_connection_info(connection_info))
                )
        else:
            # The remote Postgres case
            config_path = sdm_folder / "config.yml"
            config_data = self._load_config_yml(config_path)
            if config_data["engine"] != "postgres":
                raise ValueError(f"Unsupported engine in {config_path}: {config_data['engine']}")

            connection_description = cfg.description or config_data["description"]
            target_names = sorted(connection_names or {config_data["name"]})
            for connection_name in target_names:
                data_connection_payloads.append(
                    (
                        connection_name,
                        self._build_postgres_configuration(**config_data["configuration"]),
                    )
                )

        for connection_name, configuration in data_connection_payloads:
            await self._ensure_data_connection(
                name=connection_name,
                engine="postgres",
                configuration=configuration,
                description=connection_description,
            )

        sdm_id = await self._import_sdm(
            semantic_model, agent_id=agent_id, source_key=str(sdm_folder.resolve())
        )

        return sdm_id

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

    async def _import_sdm(
        self, semantic_model: dict[str, Any], agent_id: str | None, source_key: str
    ) -> str:
        cache_key = (source_key, agent_id)
        cached = self._import_cache.get(cache_key)
        if cached:
            return cached

        payload: dict[str, Any] = {"semantic_model": semantic_model}
        if agent_id is not None:
            payload["agent_id"] = agent_id

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

    async def _ensure_data_connection(  # noqa: C901, PLR0912, PLR0915
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
            self._log.info(
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
            self._log.info(
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
        """Interpolate $ENV_VAR_NAME patterns in config values.

        Args:
            key: Configuration field name
            value: Configuration value (may contain $ENV_VAR_NAME)
            connection_name: Data connection name (for error messages)

        Returns:
            Interpolated value with proper type conversion

        Raises:
            ValueError: If env var not found or port conversion fails
        """
        # Interpolate $ENV_VAR_NAME patterns
        if isinstance(value, str) and value.startswith("$"):
            env_var_name = value[1:]
            env_value = os.getenv(env_var_name)
            if env_value is None:
                raise ValueError(
                    f"Environment variable '{env_var_name}' not set for field '{key}' "
                    f"in data connection '{connection_name}'"
                )
            if key == "port":
                try:
                    return int(env_value)
                except ValueError as e:
                    raise ValueError(
                        f"Invalid port value from env '{env_var_name}': {env_value}"
                    ) from e
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
            raise ValueError(
                f"Invalid config.yml at {config_path}: data_connection must be a mapping"
            )
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
            raise ValueError(
                f"Missing required data connection fields in config.yml: {missing_str}"
            )

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

    def _build_postgres_configuration(  # noqa: PLR0913
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
