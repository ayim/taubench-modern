import json
from collections import defaultdict
from typing import TYPE_CHECKING
from uuid import UUID

from agent_platform.core.utils.secret_str import SecretString
from agent_platform.server.secret_manager.option import SecretService
from agent_platform.server.storage.errors import InvalidUUIDError

if TYPE_CHECKING:
    from agent_platform.server.work_items.rest import AgentWorkItemsSummaryResponse


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

    def _transform_work_items_summary_rows(self, rows) -> "list[AgentWorkItemsSummaryResponse]":
        """Transform raw work items summary rows into AgentWorkItemsSummaryResponse objects.

        Args:
            rows: List of dictionaries with agent_id, agent_name, status, count

        Returns:
            List of AgentWorkItemsSummaryResponse objects grouped by agent
        """
        from agent_platform.core.work_items.work_item import WorkItemStatus
        from agent_platform.server.work_items.rest import AgentWorkItemsSummaryResponse

        agent_summaries = {}
        for row in rows:
            agent_id = row["agent_id"]
            agent_name = row["agent_name"]
            status = row["status"]
            count = row["count"]

            if agent_id not in agent_summaries:
                agent_summaries[agent_id] = AgentWorkItemsSummaryResponse(
                    agent_id=agent_id,
                    agent_name=agent_name,
                    work_items_status_counts=defaultdict(int),
                )

            # Convert status string to WorkItemStatus enum and store count
            status_enum = WorkItemStatus(status)
            agent_summaries[agent_id].work_items_status_counts[status_enum] = count

        return list(agent_summaries.values())
