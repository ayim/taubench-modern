from pydantic import SecretStr

from agent_server_types.constants import NOT_CONFIGURED


class ConfigurationMixin:
    def is_configured(self) -> tuple[bool, list[str]]:
        fields_not_configured = []
        for field_name, field_value in self.__dict__.items():
            if isinstance(field_value, SecretStr):
                if field_value.get_secret_value() == NOT_CONFIGURED:
                    fields_not_configured.append(field_name)
            elif field_value == NOT_CONFIGURED:
                fields_not_configured.append(field_name)

        return len(fields_not_configured) == 0, fields_not_configured
