from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from agent_platform.core.model_selector.selection_request import ModelSelectionRequest

if TYPE_CHECKING:
    from agent_platform.core.platforms import PlatformClient


class ModelSelector(ABC):
    """This is a base class for implementing logic for selecting a model
    for an agent architecture.
    """

    @abstractmethod
    def override_model(self, model_id: str) -> None:
        """Override the model selection process to use a specific model."""

    @abstractmethod
    def select_model(
        self,
        platform: "PlatformClient",
        request: ModelSelectionRequest | None = None,
    ) -> str:
        """Select a model for the agent architecture.

        Args:
            selection: Optional selection criteria, which could be a model name,
                       quality tier, or other selector-specific identifier. If
                       no selection is provided, the default model for the
                       platform will be selected.

        Returns:
            The selected Model instance.

        Raises:
            ValueError: If no suitable model can be selected.
        """
