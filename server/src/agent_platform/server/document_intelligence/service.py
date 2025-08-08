from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from sema4ai.data import DataSource
from sema4ai_docint.models.constants import DATA_SOURCE_NAME

from agent_platform.core.document_intelligence.dataserver import DIDSConnectionDetails
from agent_platform.core.errors.base import PlatformError
from agent_platform.core.errors.responses import ErrorCode


@dataclass
class _DIState:
    """Internal state to track last setup configuration timestamp."""

    last_updated_at: datetime | None = None


class DocumentIntelligenceService:
    """Service for Document Intelligence data source using a singleton pattern.

    This service is responsible for ensuring the DataSource connections for
    Document Intelligence are set up exactly once for the current configuration
    (tracked by the `updated_at` field). If configuration changes, it will
    re-run the setup on next access.
    """

    _instance: ClassVar[DocumentIntelligenceService | None] = None

    def __init__(self) -> None:
        self._state = _DIState()

    @classmethod
    def get_instance(
        cls, details: DIDSConnectionDetails | None = None
    ) -> DocumentIntelligenceService:
        """Get the singleton instance of the DI service.

        If ``details`` are provided, ensure the datasource setup is performed
        (or refreshed) for the given configuration before returning the instance.
        """
        if cls._instance is None:
            cls._instance = DocumentIntelligenceService()

        if details is not None:
            cls._instance.ensure_setup(details)

        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton instance (for testing)."""
        cls._instance = None

    @classmethod
    def set_for_testing(cls, instance: DocumentIntelligenceService) -> None:
        """Set a custom instance (for testing)."""
        cls._instance = instance

    def ensure_setup(self, details: DIDSConnectionDetails) -> None:
        """Ensure the DI connections are configured for the provided details.

        The setup is re-run only if the configuration changed (based on
        `details.updated_at`).
        """
        try:
            if self._state.last_updated_at == details.updated_at:
                return

            input_json = details.as_datasource_connection_input()
            DataSource.setup_connection_from_input_json(input_json)
            self._state.last_updated_at = details.updated_at
        except Exception as e:  # pragma: no cover - error path validated via raising
            raise PlatformError(
                ErrorCode.UNEXPECTED,
                f"Error setting up Document Intelligence datasource: Error: {e}",
            ) from e

    def get_docint_datasource(self) -> DataSource:
        """Return the Document Intelligence datasource instance."""
        return DataSource.model_validate(datasource_name=DATA_SOURCE_NAME)
