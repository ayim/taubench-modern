from agent_platform.core.platforms import AnyPlatformParameters

_KIND_TO_PROVIDER: dict[str, str] = {
    "openai": "OpenAI",
    "azure": "Azure",
    "cortex": "Snowflake Cortex AI",
    "bedrock": "Amazon",
    "groq": "Groq",
    "google": "Google",
    "anthropic": "Anthropic",
    "litellm": "LiteLLM",
}

_KIND_TO_LEGACY_MODEL: dict[str, str] = {
    "openai": "gpt-4o",
    "azure": "gpt-4o",
    "cortex": "claude-3-5-sonnet",
    "bedrock": "anthropic.claude-3-5-sonnet-20240620-v1:0",
    "groq": "unknown",
    "google": "unknown",
    "anthropic": "claude-3-5-sonnet",
    "litellm": "gpt-5",
}

SENSITIVE_KEYS: list[str] = [
    "openai_api_key",
    "azure_api_key",
    "google_api_key",
    "groq_api_key",
    "anthropic_api_key",
    "chat_openai_api_key",
    "embeddings_openai_api_key",
    "aws_access_key_id",
    "aws_secret_access_key",
    "snowflake_password",
    "litellm_api_key",
]


def convert_platform_config_to_legacy_model(
    platform_configs: list[AnyPlatformParameters],
    reveal_sensitive: bool = False,
) -> dict:
    # TODO: more backwards compat, this dance will go away
    # when we have some good time to focus on studio integration
    # For now, if we don't round trip the "allow model during POST"
    # back to "render first platform_config as model", studio chokes

    # Fallback default to keep studio rendering happy
    model = {
        "provider": "OpenAI",
        "name": "gpt-4o",
        "config": {},
    }

    if len(platform_configs) <= 0:
        return model

    if platform_configs[0].kind not in _KIND_TO_PROVIDER:
        raise ValueError(f"Agent has invalid platform config kind: {platform_configs[0].kind}")

    model_config = platform_configs[0].model_dump()
    model_config.pop("kind", None)

    # If we have an allowlist then the legacy model name will be the
    # first name in the allowlist. Otherwise, we use the kind
    # to provider mapping.
    model_name = None
    if platform_configs[0].models:
        first_provider = next(iter(platform_configs[0].models))
        first_name = platform_configs[0].models[first_provider][0]
        model_name = first_name
    else:
        model_name = _KIND_TO_LEGACY_MODEL[platform_configs[0].kind]

    # Handle legacy: chat_url and embeddings_url for Azure
    model_config.pop("azure_endpoint_url", None)
    model_config.pop("azure_deployment_name", None)
    model_config.pop("azure_api_version", None)
    model_config.pop("azure_deployment_name_embeddings", None)
    if "azure_generated_endpoint_url" in model_config:
        model_config["chat_url"] = model_config.pop("azure_generated_endpoint_url", None)
    if "azure_generated_endpoint_url_embeddings" in model_config:
        model_config["embeddings_url"] = model_config.pop("azure_generated_endpoint_url_embeddings", None)

    # Handle legacy: chat_openai_api_key -> azure_api_key
    if "azure_api_key" in model_config:
        azure_api_key = model_config.pop("azure_api_key", None)
        model_config["chat_openai_api_key"] = azure_api_key
        model_config["embeddings_openai_api_key"] = azure_api_key

    # Handle legacy: Bedrock needs 'service-name'
    if "region_name" in model_config:
        model_config["service_name"] = "bedrock-runtime"

    # Remove UNSET values from model_config (on agent import right now
    # values are UNSET from legacy setup because a PUT comes in with
    # actual config values from studio later... ugh)
    model_config = {k: v for k, v in model_config.items() if v != "UNSET"}

    # Mask sensitive API keys if requested
    if not reveal_sensitive:
        model_config = {k: "**********" if k in SENSITIVE_KEYS else v for k, v in model_config.items()}

    return dict(
        provider=_KIND_TO_PROVIDER[platform_configs[0].kind],
        name=model_name,
        config=model_config,
    )
