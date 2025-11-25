from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from agent_platform.core.model_selector.base import ModelSelector
from agent_platform.core.model_selector.selection_request import ModelSelectionRequest
from agent_platform.core.platforms.configs import (
    PlatformModelConfigs,
    get_model_metadata_by_generic_id,
)
from agent_platform.core.platforms.llms_metadata_models import LLMModelMetadata

if TYPE_CHECKING:
    from agent_platform.core.platforms import PlatformClient


logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@dataclass(kw_only=True)
class ModelCandidate:
    """A candidate model with its metadata for selection."""

    generic_id: str
    provider: str
    platform_specific_id: str
    model_type: str
    model_family: str
    metadata: LLMModelMetadata | None = None
    quality_score: float = 0.0
    speed_score: float = 0.0
    cost_score: float = 0.0

    def __post_init__(self):
        """Load metadata and calculate scores after initialization."""
        self.metadata = get_model_metadata_by_generic_id(self.generic_id)
        self.quality_score = self._calculate_quality_score()
        self.speed_score = self._calculate_speed_score()
        self.cost_score = self._calculate_cost_score()

    def _calculate_quality_score(self) -> float:
        """Calculate a quality score based on artificial_analysis_intelligence_index.

        Uses the standardized intelligence index from llms.json metadata.
        Higher scores indicate higher quality models.
        """
        if not self.metadata:
            # If no metadata available, use a baseline score
            return 0.0

        # Use the artificial analysis intelligence index as the quality score
        intelligence_index = self.metadata.evaluations.artificial_analysis_intelligence_index

        if isinstance(intelligence_index, int | float):
            return float(intelligence_index)

        # Fallback to 0 if no intelligence index available
        return 0.0

    def _calculate_speed_score(self) -> float:
        """Calculate speed score based on median_output_tokens_per_second.

        Uses tokens per second from llms.json metadata.
        Higher scores indicate faster models.
        """
        if not self.metadata:
            return 0.0

        speed = self.metadata.median_output_tokens_per_second

        if isinstance(speed, int | float):
            return float(speed)

        return 0.0

    def _calculate_cost_score(self) -> float:
        """Calculate cost score based on price_1m_blended_3_to_1.

        Uses pricing from llms.json metadata.
        Returns the raw price - lower prices are better for cost optimization.
        """
        if not self.metadata:
            return float("inf")  # No metadata = expensive

        cost = self.metadata.pricing.price_1m_blended_3_to_1

        if isinstance(cost, int | float):
            return float(cost)

        return float("inf")  # No pricing data = expensive


@dataclass
class DefaultModelSelector(ModelSelector):
    def __init__(self):
        super().__init__()
        self._override_model_id: str | None = None

    def override_model(self, model_id: str) -> None:
        """Override the model selection process to use a specific model.

        Args:
            model_id: The model id to override the selection process with. MUST
                be in the format platform/provider/model. (One of our generic model ids.)
        """
        self._override_model_id = model_id

    def _handle_litellm_special_case(
        self, platform: "PlatformClient", request: ModelSelectionRequest
    ) -> str | None:
        """Handle the special case of LiteLLM."""
        if platform.name != "litellm":
            return None

        providers = list((platform.parameters.models or {}).keys())
        if not providers:
            return self._fallback_to_default(platform, request)
        elif len(providers) > 1:
            return self._fallback_to_default(platform, request)

        only_provider = providers[0]
        models = platform.parameters.models[only_provider]
        if not models:
            return self._fallback_to_default(platform, request)
        elif len(models) > 1:
            return self._fallback_to_default(platform, request)

        only_model = models[0]
        return f"litellm/{only_provider}/{only_model}"

    def select_model(
        self,
        platform: "PlatformClient",
        request: ModelSelectionRequest | None = None,
    ) -> str:
        """Select the best model based on request criteria and quality metadata.

        Selection process:
        1. Start with all models available on the platform
        2. Apply filters based on request (model type, direct name, etc.)
        3. Sort by quality score (highest first) unless prioritizing speed/cost
        4. Select the best match
        """
        if request is None:
            request = ModelSelectionRequest()

        logger.info(f"Starting model selection - platform: {platform.name}, request: {request}")

        # Step 0.9: LiteLLM is "special" we don't know candidate models ahead of time (it's
        # an "any model goes" gateway).
        if litellm_candidate := self._handle_litellm_special_case(platform, request):
            logger.info(f"LiteLLM special case detected, returning candidate: {litellm_candidate}")
            return litellm_candidate

        # Step 1: Collect all candidate models
        candidates = self._collect_all_candidates(platform)
        logger.info(f"Found {len(candidates)} total model candidates")

        # Step 1.5... if we have an override model id, use it
        if self._override_model_id:
            logger.info(f"Using override model id: {self._override_model_id}")
            if self._override_model_id.count("/") != 2:  # noqa: PLR2004 (platform/provider/model)
                raise ValueError(
                    f"Invalid override model id: {self._override_model_id};"
                    "must be in the format platform/provider/model"
                )
            candidates = [c for c in candidates if c.generic_id == self._override_model_id]
            if not candidates:
                raise ValueError(
                    f"Override model id {self._override_model_id} not found in candidates:"
                    f" [{','.join([c.generic_id for c in candidates])}]"
                )
            logger.info(f"Found {len(candidates)} candidates after override")
            return self._override_model_id

        # Step 2: Apply allowlist filter (platform restrictions)
        candidates = self._apply_allowlist_filter(platform, candidates)
        logger.info(f"After allowlist filtering: {len(candidates)} candidates remain")

        # Early exit if no candidates
        if not candidates:
            return self._fallback_to_default(platform, request)

        # Step 3: Apply request-based filters
        candidates = self._apply_request_filters(request, candidates)
        remaining_models = [c.generic_id for c in candidates]
        logger.info(
            f"After request filtering: {len(candidates)} candidates "
            f"remain - models: {remaining_models}"
        )

        # Early exit if no candidates after filtering
        if not candidates:
            logger.warning("No models match the selection criteria, falling back to default")
            return self._fallback_to_default(platform, request)

        # Early exit if only one candidate
        if len(candidates) == 1:
            selected = candidates[0]
            logger.info(
                f"Single candidate remaining, selecting it - "
                f"model: {selected.generic_id}, quality_score: {selected.quality_score}"
            )
            return selected.generic_id

        # Step 4: Sort candidates based on prioritization
        candidates = self._sort_candidates(request, candidates)

        # Step 5: Select the best candidate
        selected = candidates[0]
        runner_up = candidates[1].generic_id if len(candidates) > 1 else None
        logger.info(
            f"Model selection complete - "
            f"selected: {selected.generic_id}, quality_score: {selected.quality_score}, "
            f"type: {selected.model_type}, family: {selected.model_family}, "
            f"total_considered: {len(candidates)}, runner_up: {runner_up}"
        )

        return selected.generic_id

    def _collect_all_candidates(self, platform: "PlatformClient") -> list[ModelCandidate]:
        """Collect all possible model candidates for the platform."""
        config = PlatformModelConfigs()
        candidates = []

        # Get all models that could potentially run on this platform
        for (
            generic_id,
            platform_specific_id,
        ) in config.models_to_platform_specific_model_ids.items():
            # Check if this model is for the current platform
            if not generic_id.startswith(f"{platform.name}/"):
                continue

            # Extract provider from generic_id (platform/provider/model)
            parts = generic_id.split("/")
            if len(parts) != 3:  # noqa: PLR2004 (platform/provider/model --> 3 parts)
                continue

            provider = parts[1]
            model_type = config.models_to_model_types.get(generic_id, "unknown")
            model_family = config.models_to_families.get(generic_id, "unknown")

            candidate = ModelCandidate(
                generic_id=generic_id,
                provider=provider,
                platform_specific_id=platform_specific_id,
                model_type=model_type,
                model_family=model_family,
            )
            candidates.append(candidate)

        return candidates

    def _apply_allowlist_filter(
        self, platform: "PlatformClient", candidates: list[ModelCandidate]
    ) -> list[ModelCandidate]:
        """Filter candidates based on platform allowlist."""
        allowed_providers_and_models = platform.parameters.models or {}

        # If no allowlist, return all candidates
        if not allowed_providers_and_models:
            logger.debug("No allowlist configured, keeping all candidates")
            return candidates

        # Create set of allowed (provider, platform_specific_id) pairs
        allowed_models = set()
        for provider, models in allowed_providers_and_models.items():
            for model in models:
                allowed_models.add((provider.lower(), model))

        filtered_candidates = []
        for candidate in candidates:
            just_model = candidate.generic_id.split("/")[-1]
            if (candidate.provider.lower(), just_model) in allowed_models:
                filtered_candidates.append(candidate)
            elif (candidate.provider.lower(), candidate.generic_id) in allowed_models:
                filtered_candidates.append(candidate)
            else:
                logger.debug(
                    f"Candidate filtered out by allowlist - "
                    f"model: {candidate.generic_id}, provider: {candidate.provider}"
                )

        return filtered_candidates

    def _apply_request_filters(
        self, request: ModelSelectionRequest, candidates: list[ModelCandidate]
    ) -> list[ModelCandidate]:
        """Apply filters based on the selection request."""
        filtered_candidates = list(candidates)  # Start with all candidates

        # Filter by direct model name if specified
        if request.direct_model_name:
            logger.debug(f"Filtering by direct model name: {request.direct_model_name}")
            target_name = request.direct_model_name
            filtered_candidates = [
                c
                for c in filtered_candidates
                if c.generic_id == target_name or c.generic_id.endswith(f"/{target_name}")
            ]
            if not filtered_candidates:
                logger.warning(
                    f"Direct model name {request.direct_model_name} not found in candidates"
                )

        # Filter by model type if specified
        if request.model_type:
            logger.debug(f"Filtering by model type: {request.model_type}")
            filtered_candidates = [
                c for c in filtered_candidates if c.model_type == request.model_type
            ]
            if not filtered_candidates:
                logger.warning(f"No models found with type {request.model_type}")

        return filtered_candidates

    def _sort_candidates(
        self, request: ModelSelectionRequest, candidates: list[ModelCandidate]
    ) -> list[ModelCandidate]:
        """Sort candidates based on prioritization criteria."""
        prioritize = request.prioritize or "intelligence"  # Default to intelligence

        logger.debug(f"Sorting candidates by: {prioritize}")

        if prioritize == "intelligence":
            # Sort by intelligence score (highest first)
            sorted_candidates = sorted(candidates, key=lambda c: c.quality_score, reverse=True)
        elif prioritize == "speed":
            # Sort by speed score (highest first)
            sorted_candidates = sorted(candidates, key=lambda c: c.speed_score, reverse=True)
        elif prioritize == "cost":
            # Sort by cost score (lowest first)
            sorted_candidates = sorted(candidates, key=lambda c: c.cost_score, reverse=False)
        else:
            # Unknown prioritization, default to intelligence
            logger.warning(f"Unknown prioritization '{prioritize}', defaulting to intelligence")
            sorted_candidates = sorted(candidates, key=lambda c: c.quality_score, reverse=True)

        # Log the ranking
        for i, candidate in enumerate(sorted_candidates[:3]):  # Top 3
            metric_value = "N/A"
            if prioritize == "intelligence":
                metric_value = f"{candidate.quality_score:.1f}"
            elif prioritize == "speed":
                metric_value = f"{candidate.speed_score:.1f} tokens/sec"
            elif prioritize == "cost":
                if candidate.cost_score == float("inf"):
                    metric_value = "N/A"
                else:
                    metric_value = f"${candidate.cost_score:.2f}"

            logger.debug(
                f"Rank {i + 1}: {candidate.generic_id} - {prioritize}: {metric_value} - "
                f"type: {candidate.model_type} - has_metadata: {candidate.metadata is not None}"
            )

        return sorted_candidates

    def _fallback_to_default(
        self, platform: "PlatformClient", request: ModelSelectionRequest
    ) -> str:
        """Fallback to default model when no candidates are available."""
        # Try direct model name first if provided
        if request.direct_model_name:
            logger.info(f"Using direct model name as fallback: {request.direct_model_name}")
            return request.direct_model_name

        # Use platform default
        config = PlatformModelConfigs()
        default_model = config.platforms_to_default_model.get(platform.name)

        if not default_model:
            raise ValueError(f"No default model configured for platform {platform.name}")

        logger.info(
            f"Using platform default model as fallback: {default_model} "
            f"for platform: {platform.name}"
        )
        return default_model
