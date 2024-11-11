from pydantic import SecretStr

from agent_server_types.constants import NOT_CONFIGURED


class ConfigurationMixin:
    def is_configured(self) -> tuple[bool, list[str]]:
        """
        Checks if all fields in the object are configured.

        This method iterates over all fields in the object's dictionary. If
        a field is an instance of `SecretStr` and its value is `NOT_CONFIGURED`,
        or if the field's value is directly `NOT_CONFIGURED`, it is considered
        not configured.

        Returns:
            tuple[bool, list[str]]: A tuple where the first element is a boolean
                indicating if all fields are configured (True) or not (False), and the
                second element is a list of field names that are not configured.
        """
        fields_not_configured = []
        for field_name, field_value in self.__dict__.items():
            if isinstance(field_value, SecretStr):
                if field_value.get_secret_value() == NOT_CONFIGURED:
                    fields_not_configured.append(field_name)
            elif field_value == NOT_CONFIGURED:
                fields_not_configured.append(field_name)

        return len(fields_not_configured) == 0, fields_not_configured
