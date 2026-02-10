from __future__ import annotations

from dataclasses import dataclass, field

from agent_platform.core.document_intelligence.integrations import IntegrationKind
from agent_platform.core.integrations import Integration
from agent_platform.core.utils import SecretString
from agent_platform.core.utils.dataclass_meta import TolerantDataclass


@dataclass(frozen=True)
class IntegrationInput:
    type: str | IntegrationKind
    endpoint: str
    api_key: str | SecretString
    external_id: str | None = None


@dataclass(frozen=True)
class DocumentIntelligenceConfigPayload(TolerantDataclass):
    """Payload for upserting Document Intelligence configuration.

    Contains the Reducto integration details (endpoint + API key).
    """

    integrations: list[IntegrationInput] = field(default_factory=list)

    @staticmethod
    def _convert_integrations_to_inputs(
        integrations: list[Integration] | None,
    ) -> list[IntegrationInput]:
        """Convert Integration objects to IntegrationInput objects."""
        integration_inputs = []
        if integrations:
            from agent_platform.core.integrations.settings.reducto import ReductoSettings

            for integration in integrations:
                if isinstance(integration.settings, ReductoSettings):
                    integration_inputs.append(
                        IntegrationInput(
                            external_id=integration.settings.external_id,
                            type=integration.kind,
                            endpoint=integration.settings.endpoint,
                            api_key=integration.settings.api_key,
                        )
                    )
        return integration_inputs

    @classmethod
    def from_storage(
        cls,
        integrations: list[Integration] | None = None,
    ) -> DocumentIntelligenceConfigPayload:
        """Create DocumentIntelligenceConfigPayload from stored integration data.

        Args:
            integrations: List of integrations from v2_integration table

        Returns:
            A DocumentIntelligenceConfigPayload instance
        """
        integration_inputs = cls._convert_integrations_to_inputs(integrations)

        return cls(
            integrations=integration_inputs,
        )
