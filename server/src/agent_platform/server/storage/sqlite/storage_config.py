import json
import uuid
from datetime import datetime

from structlog import get_logger

from agent_platform.core.config.config import Config
from agent_platform.core.configurations.config_validation import ConfigType, validate_config_type
from agent_platform.server.storage.common import CommonMixin
from agent_platform.server.storage.errors import ConfigNotFoundError
from agent_platform.server.storage.sqlite.cursor import CursorMixin


class SQLiteStorageConfigMixin(CursorMixin, CommonMixin):
    """
    Mixin providing SQLite-based config operations
    """

    _logger = get_logger(__name__)

    async def list_all_configs(self) -> list[Config]:
        """List all agent configs"""
        async with self._cursor() as cur:
            await cur.execute("SELECT * FROM v2_agent_config")
            rows = await cur.fetchall()
        if not rows:
            return []
        return [Config.model_validate(dict(row)) for row in rows]

    async def get_config(self, config_type: ConfigType) -> Config:
        validate_config_type(config_type)

        async with self._cursor() as cur:
            await cur.execute(
                """
                SELECT
                *
                FROM v2_agent_config
                WHERE config_type = :config_type
                """,
                {"config_type": config_type},
            )
            row = await cur.fetchone()

        if not row:
            raise ConfigNotFoundError(config_type)
        row_dict = dict(row)
        return Config.model_validate(row_dict)

    async def set_config(self, config_type: ConfigType, current_value: str):
        validate_config_type(config_type)

        config_value = json.dumps({"current": current_value})
        record_id = str(uuid.uuid4())
        updated_at = datetime.utcnow().isoformat()

        async with self._cursor() as cur:
            await cur.execute(
                """
                INSERT INTO v2_agent_config (id, config_type, config_value, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(config_type) DO UPDATE SET
                    config_value = excluded.config_value,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (record_id, config_type, config_value, updated_at),
            )
