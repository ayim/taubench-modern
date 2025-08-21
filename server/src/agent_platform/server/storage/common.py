import json
from uuid import UUID

from agent_platform.core.utils.secret_str import SecretString
from agent_platform.server.secret_manager.option import SecretService
from agent_platform.server.storage.errors import InvalidUUIDError


class CommonMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialize secret manager once and reuse it
        self._secret_manager = SecretService.get_instance()

    def _validate_uuid(self, uuid: str) -> None:
        """Validate a UUID string."""
        try:
            UUID(uuid)
        except ValueError as e:
            raise InvalidUUIDError(f"Invalid UUID: {uuid}") from e

    # Helper methods for config encryption and decryption
    def _encrypt_config(self, config_dict: dict) -> str:
        """Encrypt the input config dictionary using the secret manager."""
        config_json = json.dumps(config_dict, sort_keys=True)
        return self._secret_manager.store(config_json)

    def _decrypt_config(self, encrypted_config: str) -> dict:
        """Decrypt the input config using the secret manager and return as dictionary."""
        decrypted_json = self._secret_manager.fetch(encrypted_config)
        return json.loads(decrypted_json)

    def _encrypt_secret_string(self, secret_string: SecretString | str) -> str:
        """Encrypt the input secret string using the secret manager."""
        if isinstance(secret_string, SecretString):
            return self._secret_manager.store(secret_string.get_secret_value())
        else:
            return self._secret_manager.store(secret_string)

    def _decrypt_secret_string(self, encrypted_secret_string: str) -> SecretString:
        """Decrypt the input secret string using the secret manager."""
        decrypted_json = self._secret_manager.fetch(encrypted_secret_string)
        return SecretString(decrypted_json)
