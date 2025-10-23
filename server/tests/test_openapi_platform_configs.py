from agent_platform.server.api.private_v2 import PRIVATE_V2_PREFIX
from agent_platform.server.app import create_app
from agent_platform.server.cli.openapi import find_mounted_app


def test_openapi_exposes_platform_model_catalog() -> None:
    def _error_with_schema(reason: str, schema: dict) -> str:
        return f"{reason}\nOpenAPI Schema: {schema}"

    app = create_app()
    private_v2_app = find_mounted_app(app, PRIVATE_V2_PREFIX)
    assert private_v2_app is not None, "Private v2 app not found"
    schema = private_v2_app.openapi()

    assert "components" in schema, _error_with_schema("'components' not found in schema", schema)
    assert "schemas" in schema["components"], _error_with_schema(
        "'schemas' not found in components", schema
    )
    components = schema["components"]["schemas"]

    platform_configs_schema = components["PlatformModelConfigs"]
    assert platform_configs_schema["default"]["platforms_to_default_model"]["openai"] == (
        "openai/openai/gpt-5-medium"
    )
    platform_configs_example = schema["components"]["examples"]["PlatformModelConfigs"]["value"]
    assert (
        platform_configs_example["models_to_families"]["openai/openai/gpt-5-medium"] == "openai-gpt"
    )

    platform_ids_schema = components["PlatformId"]
    assert "azure" in platform_ids_schema["enum"]

    provider_ids_schema = components["ProviderId"]
    assert "openai" in provider_ids_schema["enum"]

    generic_model_ids_schema = components["GenericModelId"]
    assert "openai/openai/gpt-5-medium" in generic_model_ids_schema["enum"]

    platform_providers_schema = components["PlatformProviders"]
    assert platform_providers_schema["properties"]["openai"]["items"]["$ref"] == (
        "#/components/schemas/ProviderId"
    )
    assert "openai" in platform_providers_schema["default"]["openai"]
    assert platform_providers_schema["additionalProperties"] is False

    catalog_schema = components["PlatformModelCatalog"]
    catalog_default = catalog_schema["default"]
    assert "openai/openai/gpt-5-medium" in catalog_default["models_by_platform"]["openai"]
    assert (
        "openai/openai/gpt-5-medium"
        in (catalog_default["models_by_platform_provider"]["openai/openai"])
    )

    catalog_example = schema["components"]["examples"]["PlatformModelCatalog"]["value"]
    assert catalog_example == catalog_default
