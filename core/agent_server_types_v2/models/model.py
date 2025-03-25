from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar, Literal, Self


@dataclass(frozen=True)
class Model:
    """Model definition."""

    name: str = field(metadata={"description": "The short name of the model."})
    """The short name of the model."""

    scoped_name: str = field(metadata={"description": "The scoped name of the model."})
    """The scoped name of the model."""

    max_input_tokens: int = field(
        metadata={"description": "The context window size in tokens."},
    )
    """The context window size in tokens."""

    max_output_tokens: int = field(
        metadata={"description": "The max output tokens."},
    )
    """The max output tokens."""

    last_updated_at: datetime = field(
        metadata={"description": "The last updated time of the model."},
    )
    """The last updated time of the model."""

    type: Literal[
        "llm",
        "embedding",
        "text-to-image",
        "text-to-speech",
        "speech-to-text",
    ] = field(
        metadata={"description": "The type of the model."},
    )
    """The type of the model."""

    deprecated: bool = field(
        metadata={"description": "Whether the model is deprecated."},
        default=False,
    )
    """Whether the model is deprecated."""

    currently_points_to: str | None = field(
        metadata={
            "description": "For model aliases that change, the model the alias "
            "currently points to.",
        },
        default=None,
    )
    """For model aliases that change, the model the alias currently points to."""

    def copy(self) -> Self:
        """Returns a deep copy of the model."""
        return Model(
            name=self.name,
            scoped_name=self.scoped_name,
            currently_points_to=self.currently_points_to,
            max_input_tokens=self.max_input_tokens,
            max_output_tokens=self.max_output_tokens,
            last_updated_at=self.last_updated_at,
            type=self.type,
            deprecated=self.deprecated,
        )

    def model_dump(self) -> dict:
        """Serializes the model to a dictionary. Useful for JSON serialization."""
        return {
            "name": self.name,
            "scoped_name": self.scoped_name,
            "currently_points_to": self.currently_points_to,
            "max_input_tokens": self.max_input_tokens,
            "max_output_tokens": self.max_output_tokens,
            "last_updated_at": self.last_updated_at.isoformat(),
            "type": self.type,
            "deprecated": self.deprecated,
        }

    @classmethod
    def model_validate(cls, data: dict) -> "Model":
        """Create a model from a dictionary."""
        data = data.copy()
        if "last_updated_at" in data and isinstance(data["last_updated_at"], str):
            data["last_updated_at"] = datetime.fromisoformat(data["last_updated_at"])
        return cls(**data)


class Models:
    """Models definition."""

    OPENAI_GPT_35_TURBO: ClassVar[Model] = Model(
        name="gpt-3.5-turbo",
        scoped_name="openai/gpt-3.5-turbo",
        currently_points_to="gpt-3.5-turbo-0125",
        max_input_tokens=16_385,
        max_output_tokens=4_096,
        last_updated_at=datetime(2024, 1, 25),
        type="llm",
        deprecated=True,
    )

    OPENAI_GPT_4: ClassVar[Model] = Model(
        name="gpt-4",
        scoped_name="openai/gpt-4",
        currently_points_to="gpt-4-0613",
        max_input_tokens=8_192,
        max_output_tokens=8_192,
        last_updated_at=datetime(2024, 6, 13),
        type="llm",
        deprecated=True,
    )

    OPENAI_GPT_4_TURBO: ClassVar[Model] = Model(
        name="gpt-4-turbo",
        scoped_name="openai/gpt-4-turbo",
        currently_points_to="gpt-4-turbo-2024-04-09",
        max_input_tokens=128_000,
        max_output_tokens=4_096,
        last_updated_at=datetime(2024, 4, 9),
        type="llm",
        deprecated=True,
    )

    OPENAI_CHATGPT_4o_LATEST: ClassVar[Model] = Model(
        name="chatgpt-4o-latest",
        scoped_name="openai/chatgpt-4o-latest",
        max_input_tokens=128_000,
        max_output_tokens=16_384,
        last_updated_at=datetime(2024, 8, 6),  # TODO: not really known?
        type="llm",
    )

    OPENAI_GPT_4o: ClassVar[Model] = Model(
        name="gpt-4o",
        scoped_name="openai/gpt-4o",
        currently_points_to="gpt-4o-2024-08-06",
        max_input_tokens=128_000,
        max_output_tokens=16_384,
        last_updated_at=datetime(2024, 8, 6),
        type="llm",
    )

    OPENAI_GPT_4o_MINI: ClassVar[Model] = Model(
        name="gpt-4o-mini",
        scoped_name="openai/gpt-4o-mini",
        currently_points_to="gpt-4o-mini-2024-07-18",
        max_input_tokens=128_000,
        max_output_tokens=16_384,
        last_updated_at=datetime(2024, 7, 18),
        type="llm",
    )

    OPENAI_GPT_o1: ClassVar[Model] = Model(
        name="gpt-o1",
        scoped_name="openai/gpt-o1",
        currently_points_to="o1-2024-12-17",
        max_input_tokens=200_000,
        max_output_tokens=100_000,
        last_updated_at=datetime(2024, 12, 17),
        type="llm",
    )

    OPENAI_GPT_o1_MINI: ClassVar[Model] = Model(
        name="gpt-o1-mini",
        scoped_name="openai/gpt-o1-mini",
        currently_points_to="o1-mini-2024-09-12",
        max_input_tokens=128_000,
        max_output_tokens=65_536,
        last_updated_at=datetime(2024, 9, 12),
        type="llm",
    )

    # TODO: We need to reconsider how the model types work considering how the platforms
    # are implemented with things like the ModelMap.
    ANTHROPIC_CLAUDE_3_5_SONNET: ClassVar[Model] = Model(
        name="claude-3-5-sonnet",
        scoped_name="anthropic/claude-3-5-sonnet",
        currently_points_to="claude-3-5-sonnet-20241022",
        max_input_tokens=200_000,
        max_output_tokens=8_192,
        last_updated_at=datetime(2024, 10, 22),
        type="llm",
    )

    ANTHROPIC_CLAUDE_3_5_HAIKU: ClassVar[Model] = Model(
        name="claude-3-5-haiku",
        scoped_name="anthropic/claude-3-5-haiku",
        currently_points_to="claude-3-5-haiku-20241022",
        max_input_tokens=200_000,
        max_output_tokens=8_192,
        last_updated_at=datetime(2024, 10, 22),
        type="llm",
    )

    # Amazon Bedrock Embedding Models
    AMAZON_TITAN_EMBED_TEXT_V2: ClassVar[Model] = Model(
        name="titan-embed-text-v2",
        scoped_name="amazon/titan-embed-text-v2",
        currently_points_to="amazon.titan-embed-text-v2:0",
        max_input_tokens=8_192,
        max_output_tokens=1_024,  # The embedding dimension
        last_updated_at=datetime(2023, 11, 1),  # Approximate date
        type="embedding",
    )

    AMAZON_TITAN_EMBED_TEXT_V1: ClassVar[Model] = Model(
        name="titan-embed-text-v1",
        scoped_name="amazon/titan-embed-text-v1",
        currently_points_to="amazon.titan-embed-text-v1",
        max_input_tokens=8_192,
        max_output_tokens=1_024,  # Could not find the exact value
        last_updated_at=datetime(2023, 5, 1),  # Approximate date
        type="embedding",
    )

    COHERE_EMBED_ENGLISH_V3: ClassVar[Model] = Model(
        name="cohere-embed-english-v3",
        scoped_name="cohere/cohere-embed-english-v3",
        currently_points_to="cohere.embed-english-v3",
        max_input_tokens=512,
        max_output_tokens=1_024,  # The embedding dimension
        last_updated_at=datetime(2023, 9, 1),  # Approximate date
        type="embedding",
    )

    COHERE_EMBED_MULTILINGUAL_V3: ClassVar[Model] = Model(
        name="cohere-embed-multilingual-v3",
        scoped_name="cohere/cohere-embed-multilingual-v3",
        currently_points_to="cohere.embed-multilingual-v3",
        max_input_tokens=512,
        max_output_tokens=1_024,  # The embedding dimension
        last_updated_at=datetime(2023, 9, 1),  # Approximate date
        type="embedding",
    )
