from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class ModelCreatorMetadata(BaseModel):
    """Information about the creator/provider of a model."""

    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    slug: str


class ModelEvaluationsMetadata(BaseModel):
    """Evaluation metrics for a model."""

    model_config = ConfigDict(extra="ignore")

    artificial_analysis_intelligence_index: float | None = None
    artificial_analysis_coding_index: float | None = None
    artificial_analysis_math_index: float | None = None
    mmlu_pro: float | None = None
    gpqa: float | None = None
    hle: float | None = None
    livecodebench: float | None = None
    scicode: float | None = None
    math_500: float | None = None
    aime: float | None = None


class ModelPricingMetadata(BaseModel):
    """Pricing information for a model."""

    model_config = ConfigDict(extra="ignore")

    price_1m_blended_3_to_1: float = Field(ge=0)
    price_1m_input_tokens: float = Field(ge=0)
    price_1m_output_tokens: float = Field(ge=0)


class LLMModelMetadata(BaseModel):
    """Complete model information from llms.json."""

    model_config = ConfigDict(extra="ignore")

    id: str
    name: str
    slug: str
    model_creator: ModelCreatorMetadata
    evaluations: ModelEvaluationsMetadata
    pricing: ModelPricingMetadata

    # Some models don't have a release date
    release_date: date | None = None

    # Performance metrics (optional as not all models have them)
    median_output_tokens_per_second: float | None = None
    median_time_to_first_token_seconds: float | None = None
    median_time_to_first_answer_token: float | None = None


class PromptOptionsMetadata(BaseModel):
    """Configuration for prompt options."""

    model_config = ConfigDict(extra="ignore")

    parallel_queries: int = Field(ge=1)
    prompt_length: int = Field(ge=1)


class LLMsMetadata(BaseModel):
    """Complete structure of the llms.json file."""

    model_config = ConfigDict(extra="ignore")

    status: int = Field(ge=200, le=299)
    prompt_options: PromptOptionsMetadata
    data: list[LLMModelMetadata]
