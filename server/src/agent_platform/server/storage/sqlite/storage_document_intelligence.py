import json

from sqlalchemy import delete, insert

from agent_platform.core.data_server.data_server import DataServerDetails
from agent_platform.server.storage.base import BaseStorage


class SQLiteStorageDocumentIntelligenceMixin(BaseStorage):
    """Mixin for SQLite-specific document intelligence operations."""

    async def set_dids_connection_details(self, details: DataServerDetails) -> None:
        """Set the Document Intelligence Data Server connection details."""
        dids_connection_details = self._get_table("dids_connection_details")

        async with self._write_connection() as conn:
            # Since we only store one row, clear the table first
            delete_stmt = delete(dids_connection_details)
            await conn.execute(delete_stmt)

            details_data = {
                "username": details.username,
                "updated_at": details.updated_at,
                "data_server_endpoints": json.dumps(
                    [conn.model_dump(mode="json") for conn in details.data_server_endpoints]
                ),
            }

            # Encrypt the password field for database storage
            details_data["enc_password"] = (
                self._encrypt_secret_string(details.password)
                if details.password is not None
                else None
            )

            # Insert the new connection details
            insert_stmt = insert(dids_connection_details).values(details_data)
            await conn.execute(insert_stmt)
