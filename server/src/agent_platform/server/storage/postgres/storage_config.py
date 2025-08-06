import json

from agent_platform.core.config.config import Config
from agent_platform.core.configurations.config_validation import ConfigType, validate_config_type
from agent_platform.server.storage.errors import ConfigNotFoundError
from agent_platform.server.storage.postgres.common import CommonMixin


class PostgresStorageConfigMixin(CommonMixin):
    """Mixin for PostgreSQL config operations"""

    async def list_all_configs(self) -> list[Config]:
        async with self._cursor() as cur:
            await cur.execute("SELECT * FROM v2.agent_config")
            if not (rows := await cur.fetchall()):
                return []
            configs = []
            for row in rows:
                row_dict = dict(row)
                if isinstance(row_dict["config_value"], dict):
                    row_dict["config_value"] = json.dumps(row_dict["config_value"])
                configs.append(Config.model_validate(row_dict))
            return configs

    async def get_config(self, config_type: ConfigType) -> Config:
        validate_config_type(config_type)

        async with self._cursor() as cur:
            await cur.execute(
                """SELECT
                *
                FROM v2.agent_config
                WHERE config_type = %(config_type)""",
                {"config_type": config_type},
            )

            if not (row := await cur.fetchone()):
                raise ConfigNotFoundError(config_type)

            row_dict = dict(row)
            if isinstance(row_dict["config_value"], dict):
                row_dict["config_value"] = json.dumps(row_dict["config_value"])
            return Config.model_validate(row_dict)

    async def set_config(self, config_type: ConfigType, current_value: str):
        validate_config_type(config_type)

        config_value = json.dumps({"current": current_value})

        async with self._cursor() as cur:
            await cur.execute(
                """
                INSERT INTO v2.agent_config (config_type, config_value)
                VALUES (%(config_type)s, %(config_value)s)
                ON CONFLICT (config_type)
                DO UPDATE SET
                    config_value = EXCLUDED.config_value,
                    updated_at = now()
                """,
                {"config_type": config_type, "config_value": config_value},
            )
