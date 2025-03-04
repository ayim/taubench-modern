from abc import ABC, abstractmethod

from agent_server_types_v2.kernel_interfaces.kernel_mixin import UsesKernelMixin
from agent_server_types_v2.models import Model


class ModelSelector(ABC, UsesKernelMixin):
    """This is a base class for implementing logic for selecting a model
    for an agent architecture.
    """

    @abstractmethod
    def select_model(self, selection: str | None = None) -> Model:
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
        pass
