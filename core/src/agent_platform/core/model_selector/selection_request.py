from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ModelSelectionRequest:
    """A request for a model selection base on
    provider, model_type, and quality_tier.

    Alternatively, a direct model name can be provided.
    """

    direct_model_name: str | None = None
    provider: str | None = None
    model_type: Literal[
        "llm", "embedding", "text-to-image", "text-to-audio", "audio-to-text",
    ] | None = None
    quality_tier: Literal["best", "balanced", "fastest"] | None = None

    def is_empty(self) -> bool:
        return (
            self.direct_model_name is None
            and self.provider is None
            and self.model_type is None
            and self.quality_tier is None
        )
