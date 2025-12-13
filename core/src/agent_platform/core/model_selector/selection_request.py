from dataclasses import dataclass

from agent_platform.core.platforms.configs import ModelPrioritization, ModelType


@dataclass(frozen=True)
class ModelSelectionRequest:
    """A request for a model selection.

    This request can be empty, in which case the default model for the platform
    will be used.

    Alternatively, a direct model name and/or model type can be provided.
    """

    direct_model_name: str | None = None
    model_type: ModelType | None = None
    prioritize: ModelPrioritization | None = None

    def is_empty(self) -> bool:
        return self.direct_model_name is None and self.model_type is None and self.prioritize is None
