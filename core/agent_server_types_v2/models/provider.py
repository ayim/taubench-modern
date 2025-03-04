from dataclasses import dataclass, field
from typing import ClassVar, Self

from agent_server_types_v2.models.model import Model, Models


@dataclass(frozen=True)
class ModelProvider:
    """Model provider definition."""

    name: str = field(metadata={"description": "The name of the provider."})
    """The name of the provider."""

    supported_models: list[Model] = field(
        metadata={"description": "The models we support from the provider."},
        default_factory=list,
    )
    """The models we support from the provider."""

    def to_json_dict(self) -> dict:
        """Serializes the model provider to a dictionary.
        Useful for JSON serialization."""
        return {
            "name": self.name,
            "supported_models": [
                model.to_json_dict() for model in self.supported_models
            ],
        }

    def copy(self) -> Self:
        """Returns a deep copy of the model provider."""
        return ModelProvider(
            name=self.name,
            supported_models=[model.copy() for model in self.supported_models],
        )

    @classmethod
    def from_dict(cls, data: dict) -> "ModelProvider":
        """Create a model provider from a dictionary."""
        data = data.copy()
        supported_models = [
            Model.from_dict(model) for model in data.pop("supported_models", [])
        ]
        return cls(**data, supported_models=supported_models)


class ModelProviders:
    """Model providers definition."""

    OPENAI: ClassVar[ModelProvider] = ModelProvider(
        name="openai",
        supported_models=[
            Models.OPENAI_GPT_35_TURBO,
            Models.OPENAI_GPT_4,
            Models.OPENAI_GPT_4_TURBO,
            Models.OPENAI_CHATGPT_4o_LATEST,
            Models.OPENAI_GPT_4o,
            Models.OPENAI_GPT_4o_MINI,
            Models.OPENAI_GPT_o1,
            Models.OPENAI_GPT_o1_MINI,
        ],
    )

    ANTHROPIC: ClassVar[ModelProvider] = ModelProvider(
        name="anthropic",
        supported_models=[
            Models.ANTHROPIC_CLAUDE_3_5_SONNET,
            Models.ANTHROPIC_CLAUDE_3_5_HAIKU,
        ],
    )
