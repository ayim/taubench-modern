import json
from abc import abstractmethod
from contextlib import AbstractAsyncContextManager
from uuid import UUID

from psycopg import AsyncCursor
from psycopg.rows import DictRow

from agent_platform.server.secret_manager.option import SecretService
from agent_platform.server.storage.base import BaseStorage
from agent_platform.server.storage.errors import InvalidUUIDError


class CommonMixin(BaseStorage):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialize secret manager once and reuse it
        self._secret_manager = SecretService.get_instance()

    @abstractmethod
    def _cursor(
        self,
        cursor: AsyncCursor[DictRow] | None = None,
    ) -> AbstractAsyncContextManager[AsyncCursor[DictRow]]:
        """Get a cursor for the database (or uses the provided cursor)."""
        pass

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
