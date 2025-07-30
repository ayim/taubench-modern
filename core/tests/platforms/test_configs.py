from typing import get_args

import pytest

from agent_platform.core.platforms.configs import (
    ModelType,
    PlatformModelConfigs,
    get_model_metadata_by_generic_id,
    get_model_metadata_by_slug,
)


@pytest.fixture(autouse=True)
def _load_metadata():
    from agent_platform.core.platforms.llms_metadata_loader import llms_metadata_loader

    llms_metadata_loader.load_data()


class TestPlatformModelConfigs:
    """Test suite for PlatformModelConfigs consistency and validation."""

    def test_keys_consistency_across_major_dicts(self):
        """Test that keys are consistent across the major dictionaries in PlatformModelConfigs.

        This test ensures that:
        1. All models in models_capable_of_driving_agents have entries in
        models_to_platform_specific_model_ids
        2. All models in models_capable_of_driving_agents have entries in
        models_to_families
        3. All default models in platforms_to_default_model have entries in the
        other dictionaries
        4. Keys in models_to_platform_specific_model_ids and models_to_families
        match exactly
        """
        config = PlatformModelConfigs()

        # Get all the relevant collections
        capable_models = set(config.models_capable_of_driving_agents)
        default_models = set(config.platforms_to_default_model.values())
        platform_specific_keys = set(config.models_to_platform_specific_model_ids.keys())
        family_keys = set(config.models_to_families.keys())

        # Test 1: All models capable of driving agents should have platform-specific mappings
        missing_platform_specific = capable_models - platform_specific_keys
        assert not missing_platform_specific, (
            f"Models in models_capable_of_driving_agents missing from "
            f"models_to_platform_specific_model_ids: {missing_platform_specific}"
        )

        # Test 2: All models capable of driving agents should have family mappings
        missing_family = capable_models - family_keys
        assert not missing_family, (
            f"Models in models_capable_of_driving_agents missing from "
            f"models_to_families: {missing_family}"
        )

        # Test 3: All default models should have platform-specific mappings
        missing_default_platform_specific = default_models - platform_specific_keys
        assert not missing_default_platform_specific, (
            f"Default models in platforms_to_default_model missing from "
            f"models_to_platform_specific_model_ids: {missing_default_platform_specific}"
        )

        # Test 4: All default models should have family mappings
        missing_default_family = default_models - family_keys
        assert not missing_default_family, (
            f"Default models in platforms_to_default_model missing from "
            f"models_to_families: {missing_default_family}"
        )

        # Test 5: Keys in models_to_platform_specific_model_ids and models_to_families
        # should match exactly
        platform_specific_only = platform_specific_keys - family_keys
        family_only = family_keys - platform_specific_keys

        assert not platform_specific_only, (
            f"Models in models_to_platform_specific_model_ids but not in models_to_families: "
            f"{platform_specific_only}"
        )

        assert not family_only, (
            f"Models in models_to_families but not in models_to_platform_specific_model_ids: "
            f"{family_only}"
        )

    def test_all_models_have_type_assignments(self):
        """Test that all models in the configuration have type assignments.

        This ensures that every model configured in the system has a corresponding
        entry in models_to_model_types.
        """
        config = PlatformModelConfigs()

        # Collect all unique model IDs from all configuration dictionaries
        all_configured_models = set()
        all_configured_models.update(config.models_capable_of_driving_agents)
        all_configured_models.update(config.platforms_to_default_model.values())
        all_configured_models.update(config.models_to_platform_specific_model_ids.keys())
        all_configured_models.update(config.models_to_families.keys())

        # Get all models that have type assignments
        typed_models = set(config.models_to_model_types.keys())

        # Find models without type assignments
        missing_types = all_configured_models - typed_models
        assert not missing_types, (
            f"The following models are configured but missing type assignments: "
            f"{missing_types}. Add them to models_to_model_types."
        )

        # Find type assignments for models not in other configs (orphaned types)
        orphaned_types = typed_models - all_configured_models
        assert not orphaned_types, (
            f"The following models have type assignments but are not configured anywhere else: "
            f"{orphaned_types}. Either add them to the configuration or remove from "
            "models_to_model_types."
        )

    def test_model_types_are_valid(self):
        """Test that all model type assignments use valid ModelType values."""
        config = PlatformModelConfigs()

        # Get the valid model types from the ModelType literal
        valid_types = set(get_args(ModelType))

        # Check all assigned types are valid
        invalid_types = []
        for model_id, model_type in config.models_to_model_types.items():
            if model_type not in valid_types:
                invalid_types.append((model_id, model_type))

        assert not invalid_types, (
            f"The following models have invalid type assignments: "
            f"{[(m_id, f'invalid type: {m_type}') for m_id, m_type in invalid_types]}. "
            f"Valid types are: {sorted(valid_types)}"
        )

    def test_generic_model_ids_have_exactly_two_slashes(self):
        """Test that all generic model IDs have exactly two '/' characters.

        Generic model IDs should follow the format: platform/provider/model
        This means they should have exactly 2 '/' characters.
        """
        config = PlatformModelConfigs()

        # Collect all generic model IDs from different sources
        all_model_ids = set()

        # From models_capable_of_driving_agents
        all_model_ids.update(config.models_capable_of_driving_agents)

        # From platforms_to_default_model values
        all_model_ids.update(config.platforms_to_default_model.values())

        # From models_to_platform_specific_model_ids keys
        all_model_ids.update(config.models_to_platform_specific_model_ids.keys())

        # From models_to_families keys
        all_model_ids.update(config.models_to_families.keys())

        # Check each model ID has exactly 2 slashes
        invalid_model_ids = []
        for model_id in all_model_ids:
            slash_count = model_id.count("/")
            if slash_count != 2:
                invalid_model_ids.append((model_id, slash_count))

        assert not invalid_model_ids, (
            f"The following model IDs do not have exactly 2 '/' characters "
            f"(expected format: platform/provider/model): "
            f"{[(model_id, f'has {count} slashes') for model_id, count in invalid_model_ids]}"
        )

    def test_all_default_models_are_capable_of_driving_agents(self):
        """Test that all default models for platforms are also in the list
        of models capable of driving agents.

        This is a logical consistency check - if a model is set as default for a platform,
        it should be capable of driving agents.
        """
        config = PlatformModelConfigs()

        # We exclude reducto here, that platform is _solely_ for document use
        # cases (not for driving agents)
        excluded_platforms = ["reducto"]
        default_models = set(
            [
                config.platforms_to_default_model[platform]
                for platform in config.platforms_to_default_model
                if platform not in excluded_platforms
            ]
        )

        capable_models = set(config.models_capable_of_driving_agents)

        missing_from_capable = default_models - capable_models
        assert not missing_from_capable, (
            f"Default models that are not in models_capable_of_driving_agents: "
            f"{missing_from_capable}. All default models should be capable of driving agents."
        )

    def test_model_id_format_validation(self):
        """Test that all generic model IDs follow the expected naming convention.

        This test validates that model IDs are properly structured with valid platform,
        provider, and model names (no empty segments, reasonable characters, etc.).
        """
        config = PlatformModelConfigs()

        # Collect all generic model IDs
        all_model_ids = set()
        all_model_ids.update(config.models_capable_of_driving_agents)
        all_model_ids.update(config.platforms_to_default_model.values())
        all_model_ids.update(config.models_to_platform_specific_model_ids.keys())
        all_model_ids.update(config.models_to_families.keys())

        invalid_model_ids = []
        for model_id in all_model_ids:
            parts = model_id.split("/")

            # Should have exactly 3 parts (platform, provider, model)
            if len(parts) != 3:
                invalid_model_ids.append((model_id, f"has {len(parts)} parts instead of 3"))
                continue

            platform, provider, model = parts

            # No part should be empty
            if not platform:
                invalid_model_ids.append((model_id, "has empty platform"))
            elif not provider:
                invalid_model_ids.append((model_id, "has empty provider"))
            elif not model:
                invalid_model_ids.append((model_id, "has empty model"))

            # Parts should not contain whitespace
            if any(" " in part or "\t" in part or "\n" in part for part in parts):
                invalid_model_ids.append((model_id, "contains whitespace in one of its parts"))

        assert not invalid_model_ids, (
            f"The following model IDs have invalid format: "
            f"{[(model_id, reason) for model_id, reason in invalid_model_ids]}"
        )

    def test_get_model_metadata_by_slug_function(self):
        """Test that get_model_metadata_by_slug works correctly."""
        # Test with a known model slug
        metadata = get_model_metadata_by_slug("gpt-4-1")
        assert metadata is not None, "Should find metadata for gpt-4-1"
        assert metadata.slug == "gpt-4-1"
        assert metadata.name, "Should find name for gpt-4-1"
        assert metadata.evaluations, "Should find evaluations for gpt-4-1"

        # Test with non-existent slug
        metadata = get_model_metadata_by_slug("non-existent-model")
        assert metadata is None, "Should return None for non-existent model"

        # Test with empty string
        metadata = get_model_metadata_by_slug("")
        assert metadata is None, "Should return None for empty string"

    def test_get_model_metadata_by_generic_id_function(self):
        """Test that get_model_metadata_by_generic_id works correctly."""

        # Test with a known generic model ID
        metadata = get_model_metadata_by_generic_id("openai/openai/gpt-4-1")
        assert metadata is not None, "Should find metadata for openai/openai/gpt-4-1"
        assert metadata.slug == "gpt-4-1"
        assert metadata.name, "Should find name for openai/openai/gpt-4-1"
        assert metadata.evaluations, "Should find evaluations for openai/openai/gpt-4-1"

        # Test with different platform, same model
        metadata = get_model_metadata_by_generic_id("azure/openai/gpt-4-1")
        assert metadata is not None, "Should find metadata for azure/openai/gpt-4-1"
        assert metadata.slug == "gpt-4-1"

        # Test with non-existent model
        metadata = get_model_metadata_by_generic_id("openai/openai/non-existent-model")
        assert metadata is None, "Should return None for non-existent model"

        # Test with invalid format (too few slashes)
        metadata = get_model_metadata_by_generic_id("openai/gpt-4-1")
        assert metadata is None, "Should return None for invalid format"

        # Test with invalid format (no slashes)
        metadata = get_model_metadata_by_generic_id("gpt-4-1")
        assert metadata is None, "Should return None for invalid format"

        # Test with empty string
        metadata = get_model_metadata_by_generic_id("")
        assert metadata is None, "Should return None for empty string"

    def test_all_configured_models_have_metadata_in_llms_json(self):
        """Test that all models in our configuration have corresponding metadata in llms.json.

        This ensures we haven't configured models that don't exist in the metadata source.
        We only check LLM models since llms.json is focused on LLM models.
        """
        config = PlatformModelConfigs()

        # Collect all unique model IDs from our configuration
        all_model_ids = set()
        all_model_ids.update(config.models_capable_of_driving_agents)
        all_model_ids.update(config.platforms_to_default_model.values())
        all_model_ids.update(config.models_to_platform_specific_model_ids.keys())

        # Filter to only LLM models based on model type
        llm_model_ids = []
        for model_id in all_model_ids:
            model_type = config.models_to_model_types.get(model_id)
            if model_type == "llm":
                llm_model_ids.append(model_id)

        # Extract unique slugs (the part after the last slash) for LLM models
        llm_slugs = set()
        for model_id in llm_model_ids:
            parts = model_id.split("/")
            if len(parts) >= 3:
                slug = parts[-1]  # Get the last part as the slug
                llm_slugs.add(slug)

        # Check which LLM models don't have metadata
        missing_metadata = []
        for slug in llm_slugs:
            metadata = get_model_metadata_by_slug(slug)
            if metadata is None:
                missing_metadata.append(slug)

        assert not missing_metadata, (
            f"The following configured LLM model slugs do not have metadata in llms.json: "
            f"{missing_metadata}. Either add them to llms.json or remove them "
            "from the configuration."
        )

    def test_metadata_consistency_for_sample_models(self):
        """Test that metadata retrieved is consistent and has expected structure."""
        # Test a few key models to ensure the metadata structure is as expected
        test_models = [
            "openai/openai/gpt-4-1",
            "google/google/gemini-2-5-pro",
            "bedrock/anthropic/claude-4-sonnet",
        ]

        for model_id in test_models:
            metadata = get_model_metadata_by_generic_id(model_id)
            if metadata is not None:  # Skip if model not found (might be expected)
                # Check model_creator structure
                assert metadata.model_creator.name, f"Model {model_id} missing creator name"
                assert metadata.model_creator.slug, f"Model {model_id} missing creator slug"

                # Verify the slug matches what we expect
                expected_slug = model_id.split("/")[-1]
                assert metadata.slug == expected_slug, (
                    f"Model {model_id} has slug {metadata.slug} but expected {expected_slug}"
                )
