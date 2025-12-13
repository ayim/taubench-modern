import json
from copy import deepcopy
from dataclasses import dataclass, field, fields
from datetime import datetime
from typing import Any
from uuid import UUID

from agent_platform.core.configurations.config_validation import ConfigType


@dataclass(frozen=True)
class Config:
    """Agent config definition"""

    id: str = field(metadata={"description": "The id of the config, Primary key"})
    config_type: ConfigType = field(metadata={"description": "The config type of this row"})
    namespace: str = field(metadata={"description": 'The namespace of the config. Defaults to "global"'})
    config_value: Any = field(metadata={"description": "The config value of the config type"})
    updated_at: datetime = field(metadata={"description": "The last update time of the config"})

    def copy(self, **updates: Any) -> "Config":
        all_field_names = {f.name for f in fields(self)}
        for key in updates:
            if key not in all_field_names:
                raise TypeError(f"'{key}' is an invalid keyword argument for copy()")

        constructor_args = {}
        for field_info in fields(self):
            field_name = field_info.name

            if field_name in updates:
                constructor_args[field_name] = deepcopy(updates[field_name])
            else:
                original_value = getattr(self, field_name)
                constructor_args[field_name] = deepcopy(original_value)

        new_agent = Config(**constructor_args)
        return new_agent

    def model_dump(self) -> dict:
        return {
            "id": self.id,
            "config_type": self.config_type.value,
            "namespace": self.namespace,
            "config_value": self.config_value,
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def model_validate(cls, data: dict) -> "Config":
        data = data.copy()

        if "id" in data and isinstance(data["id"], UUID):
            data["id"] = str(data["id"])
        if "updated_at" in data and isinstance(data["updated_at"], str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        if "config_value" in data:
            data["config_value"] = json.loads(data["config_value"])

        return cls(**data)
