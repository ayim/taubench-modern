from dataclasses import asdict
from typing import Any

from pydantic import TypeAdapter

from agent_platform.core.platforms.configs import PlatformModelConfigs

GENERIC_MODEL_ID_PARTS = 3  # platform/provider/model


def inject_platform_model_catalog(
    components: dict[str, Any],
    schemas: dict[str, Any],
    ref_template: str,
) -> None:
    """Expose PlatformModelConfigs and derived lookup tables in OpenAPI."""
    if "PlatformModelConfigs" in schemas:
        # Logic already executed for this schema build
        return

    config_schema = TypeAdapter(PlatformModelConfigs).json_schema(ref_template=ref_template)
    config_schema.pop("$defs", None)
    config_schema.setdefault(
        "description",
        (
            "Static configuration describing platform/model defaults, family mappings, and "
            "capabilities. Kept in sync with agent_platform.core.platforms.configs."
        ),
    )
    config_value = asdict(PlatformModelConfigs())
    config_schema.setdefault("default", config_value)
    config_schema.setdefault("examples", [config_value])

    schemas["PlatformModelConfigs"] = config_schema

    examples = components.setdefault("examples", {})
    examples["PlatformModelConfigs"] = {
        "summary": "Current PlatformModelConfigs",
        "description": (
            "Snapshot of the PlatformModelConfigs dataclass; treat as read-only "
            "static data published with the OpenAPI document."
        ),
        "value": config_value,
    }

    models_to_platform_specific_ids: dict[str, str] = config_value.get(
        "models_to_platform_specific_model_ids",
        {},
    )

    generic_model_ids = sorted(models_to_platform_specific_ids)

    platform_set: set[str] = set(config_value.get("platforms_to_default_model", ()))
    provider_set: set[str] = set()
    platform_provider_set: set[str] = set()
    providers_by_platform: dict[str, set[str]] = {platform: set() for platform in platform_set}
    models_by_platform: dict[str, list[str]] = {platform: [] for platform in platform_set}
    models_by_platform_provider: dict[str, list[str]] = {}

    for full_model_id in generic_model_ids:
        parts = full_model_id.split("/")
        if len(parts) != GENERIC_MODEL_ID_PARTS:
            continue
        platform, provider, _ = parts
        platform_set.add(platform)
        provider_set.add(provider)
        providers_by_platform.setdefault(platform, set()).add(provider)
        models_by_platform.setdefault(platform, []).append(full_model_id)

        platform_provider_key = f"{platform}/{provider}"
        platform_provider_set.add(platform_provider_key)
        models_by_platform_provider.setdefault(platform_provider_key, []).append(full_model_id)

    platform_ids = sorted(platform_set)
    provider_ids = sorted(provider_set)
    platform_provider_ids = sorted(platform_provider_set)

    providers_by_platform_value = {
        platform: sorted(providers_by_platform.get(platform, ())) for platform in platform_ids
    }
    models_by_platform_value = {
        platform: sorted(models_by_platform.get(platform, ())) for platform in platform_ids
    }
    models_by_platform_provider_value = {
        platform_provider: sorted(models_by_platform_provider.get(platform_provider, ()))
        for platform_provider in platform_provider_ids
    }

    schemas["PlatformId"] = {
        "type": "string",
        "enum": platform_ids,
        "description": "Identifier for a configured platform (e.g. azure, bedrock).",
    }

    schemas["ProviderId"] = {
        "type": "string",
        "enum": provider_ids,
        "description": "Identifier for a provider within a platform (e.g. openai, anthropic).",
    }

    schemas["PlatformProviderId"] = {
        "type": "string",
        "enum": platform_provider_ids,
        "description": "Identifier for a platform/provider pair in `<platform>/<provider>` form.",
    }

    schemas["GenericModelId"] = {
        "type": "string",
        "enum": generic_model_ids,
        "description": "Fully-qualified generic model ID in `<platform>/<provider>/<model>` form.",
    }

    schemas["PlatformProviders"] = {
        "type": "object",
        "properties": {
            platform: {
                "type": "array",
                "items": {"$ref": ref_template.format(model="ProviderId")},
            }
            for platform in platform_ids
        },
        "required": platform_ids,
        "additionalProperties": False,
        "description": "Maps each platform to the provider IDs it exposes.",
        "default": providers_by_platform_value,
        "examples": [providers_by_platform_value],
    }

    schemas["PlatformModelsByPlatform"] = {
        "type": "object",
        "properties": {
            platform: {
                "type": "array",
                "items": {"$ref": ref_template.format(model="GenericModelId")},
            }
            for platform in platform_ids
        },
        "required": platform_ids,
        "additionalProperties": False,
        "description": "Maps each platform to the generic model IDs it supports.",
        "default": models_by_platform_value,
        "examples": [models_by_platform_value],
    }

    schemas["PlatformModelsByPlatformProvider"] = {
        "type": "object",
        "properties": {
            platform_provider: {
                "type": "array",
                "items": {"$ref": ref_template.format(model="GenericModelId")},
            }
            for platform_provider in platform_provider_ids
        },
        "required": platform_provider_ids,
        "additionalProperties": False,
        "description": (
            "Maps each `<platform>/<provider>` pair to the generic model IDs it offers."
        ),
        "default": models_by_platform_provider_value,
        "examples": [models_by_platform_provider_value],
    }

    platform_model_catalog = {
        "platforms": platform_ids,
        "providers": provider_ids,
        "platform_provider_ids": platform_provider_ids,
        "providers_by_platform": providers_by_platform_value,
        "models_by_platform": models_by_platform_value,
        "models_by_platform_provider": models_by_platform_provider_value,
    }

    schemas["PlatformModelCatalog"] = {
        "type": "object",
        "properties": {
            "platforms": {
                "type": "array",
                "items": {"$ref": ref_template.format(model="PlatformId")},
            },
            "providers": {
                "type": "array",
                "items": {"$ref": ref_template.format(model="ProviderId")},
            },
            "platform_provider_ids": {
                "type": "array",
                "items": {"$ref": ref_template.format(model="PlatformProviderId")},
            },
            "providers_by_platform": {"$ref": ref_template.format(model="PlatformProviders")},
            "models_by_platform": {"$ref": ref_template.format(model="PlatformModelsByPlatform")},
            "models_by_platform_provider": {
                "$ref": ref_template.format(model="PlatformModelsByPlatformProvider")
            },
        },
        "required": [
            "platforms",
            "providers",
            "platform_provider_ids",
            "providers_by_platform",
            "models_by_platform",
            "models_by_platform_provider",
        ],
        "additionalProperties": False,
        "description": (
            "Precomputed lookup tables relating platforms, providers, and generic model IDs."
        ),
        "default": platform_model_catalog,
        "examples": [platform_model_catalog],
    }

    examples["PlatformModelCatalog"] = {
        "summary": "Hierarchy of platforms/providers/models",
        "description": "Static helper maps derived from PlatformModelConfigs.",
        "value": platform_model_catalog,
    }
