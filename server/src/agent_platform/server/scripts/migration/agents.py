import json
from urllib.parse import parse_qs, urlparse

import structlog

logger = structlog.get_logger(__name__)


def parse_azure_config(config: dict) -> dict:
    """
    Parse Azure configuration from v1 format to v2 format.

    Args:
        config: Dictionary containing Azure configuration with chat_url,
        embeddings_url, and chat_openai_api_key

    Returns:
        Dictionary with parsed Azure platform configuration
    """
    chat_url = config["chat_url"]
    embeddings_url = config.get("embeddings_url")
    api_key = config["chat_openai_api_key"]

    # Extract base endpoint, deployment name, and API version from chat URL
    # URL format: https://endpoint.openai.azure.com/openai/deployments/deployment-name/chat/completions?api-version=version
    chat_parsed = urlparse(chat_url)
    base_endpoint = f"{chat_parsed.scheme}://{chat_parsed.netloc}"

    # Extract deployment name from path
    path_parts = chat_parsed.path.split("/")
    chat_deployment = ""
    if "deployments" in path_parts:
        deployment_index = path_parts.index("deployments")
        if deployment_index + 1 < len(path_parts):
            chat_deployment = path_parts[deployment_index + 1]

    # Extract API version from query params
    query_params = parse_qs(chat_parsed.query)
    api_version = query_params.get("api-version", [""])[0]

    # Extract embeddings deployment name if embeddings URL exists
    embeddings_deployment = ""
    if embeddings_url:
        embeddings_parsed = urlparse(embeddings_url)
        embeddings_path_parts = embeddings_parsed.path.split("/")
        if "deployments" in embeddings_path_parts:
            embeddings_deployment_index = embeddings_path_parts.index("deployments")
            if embeddings_deployment_index + 1 < len(embeddings_path_parts):
                embeddings_deployment = embeddings_path_parts[embeddings_deployment_index + 1]

    return {
        "kind": "azure",
        "azure_api_key": api_key,
        "azure_endpoint_url": base_endpoint,
        "azure_deployment_name": chat_deployment,
        "azure_deployment_name_embeddings": embeddings_deployment,
        "azure_api_version": api_version,
        "azure_generated_endpoint_url": chat_url,
        "azure_generated_endpoint_url_embeddings": embeddings_url,
    }


def parse_platform_configs(model: str) -> list:
    """
    Parse platform configurations from v1 model format to v2 format.

    Args:
        model: JSON string or dict containing model configuration

    Returns:
        List of platform configuration dictionaries
    """
    platform_configs = []

    try:
        # Handle case where model might already be a dict instead of JSON string
        if isinstance(model, str):
            model_json = json.loads(model)
        else:
            model_json = model

        provider = model_json.get("provider", "").lower()
        config = model_json.get("config", {})

        if provider == "openai" and config.get("openai_api_key"):
            platform_configs.append({"kind": "openai", "openai_api_key": config["openai_api_key"]})
        elif provider == "amazon" and config.get("aws_access_key_id") and config.get("aws_secret_access_key"):
            platform_configs.append(
                {
                    "kind": "bedrock",
                    "region_name": config.get("region_name"),
                    "aws_access_key_id": config["aws_access_key_id"],
                    "aws_secret_access_key": config["aws_secret_access_key"],
                    "config_params": {},
                }
            )
        elif provider == "azure" and config.get("chat_url") and config.get("chat_openai_api_key"):
            platform_configs.append(parse_azure_config(config))
        elif provider == "snowflake cortex ai":
            platform_configs.append(
                {
                    "kind": "cortex",
                }
            )

    except (json.JSONDecodeError, KeyError) as e:
        raise Exception(f"Failed to parse model configuration: {e}") from e

    return platform_configs


def convert_agent_to_v2_format(v1_agent: dict) -> dict:
    def require(key: str) -> str:
        val = v1_agent.get(key)
        if not val:
            raise Exception(f"Skipping agent because it has no {key}")
        return val

    agent_id = require("id")
    agent_name = require("name")
    agent_description = require("description")
    user_id = require("user_id")
    runbook_text = require("runbook")

    runbook_structured = {"raw_text": runbook_text, "content": []}

    version = v1_agent.get("version")
    created_at = v1_agent.get("created_at")
    updated_at = v1_agent.get("updated_at")

    v1_action_packages = v1_agent.get("action_packages", [])
    # Handle case where action_packages might already be a list instead of JSON string
    if isinstance(v1_action_packages, str):
        action_packages = json.loads(v1_action_packages)
    else:
        action_packages = v1_action_packages

    mcp_servers = []
    agent_architecture = {"name": "agent_platform.architectures.default", "version": "1.0.0"}

    metadata = v1_agent.get("metadata", {})
    # Handle case where metadata might already be a dict instead of JSON string
    if isinstance(metadata, str):
        metadata_json = json.loads(metadata)
    else:
        metadata_json = metadata
    question_groups = metadata_json.get("question_groups", [])

    v1_agent_advanced_config = v1_agent.get("advanced_config", {})
    # Handle case where advanced_config might already be a dict instead of JSON string
    if isinstance(v1_agent_advanced_config, str):
        v1_agent_advanced_config_json = json.loads(v1_agent_advanced_config)
    else:
        v1_agent_advanced_config_json = v1_agent_advanced_config
    langsmith_config = v1_agent_advanced_config_json.get("langsmith", {})

    model = v1_agent.get("model")

    observability_configs = []
    if langsmith_config:
        api_key = langsmith_config.get("api_key", "")
        project_name = langsmith_config.get("project_name", "")
        if api_key and project_name:
            observability_configs.append(
                {
                    "type": "langsmith",
                    "api_key": api_key,
                    "api_url": langsmith_config.get("api_url", "https://api.smith.langchain.com"),
                    "settings": {"project_name": project_name},
                }
            )

    platform_configs = []

    if model:
        try:
            platform_configs = parse_platform_configs(model)
        except Exception as e:
            logger.error(f"Failed to parse platform configs for model {model}: {e}")
            platform_configs = []

    extra = {}

    mode = metadata_json.get("mode", "conversational")

    agent_dict = {
        "agent_id": agent_id,
        "name": agent_name,
        "description": agent_description,
        "user_id": user_id,
        "runbook_structured": runbook_structured,
        "version": version,
        "created_at": created_at,
        "updated_at": updated_at,
        "action_packages": action_packages,
        "mcp_servers": mcp_servers,
        "agent_architecture": agent_architecture,
        "question_groups": question_groups,
        "observability_configs": observability_configs,
        "platform_configs": platform_configs,
        "extra": extra,
        "mode": mode,
    }

    for field in [
        "runbook_structured",
        "action_packages",
        "mcp_servers",
        "agent_architecture",
        "question_groups",
        "observability_configs",
        "platform_configs",
        "extra",
    ]:
        agent_dict[field] = json.dumps(agent_dict.get(field))

    return agent_dict


async def migrate_agents(storage):
    """
    Migrate agents using the provided storage connection
    Args:
        storage: Connected storage interface
    """
    try:
        agents = await storage.get_all_agents()

        for v1_agent in agents:
            try:
                agent_dict = convert_agent_to_v2_format(v1_agent)
            except Exception as e:
                logger.error(f"Error converting agent: {e}")
                continue

            try:
                await storage.insert_agent(agent_dict)
                logger.info(f"Successfully migrated agent: {v1_agent['name']}")
            except Exception as e:
                logger.error(f"Error migrating agent {v1_agent['name']}: {e}")

    except Exception as e:
        logger.error(f"Error during agents migration: {e}")
        raise

    logger.info("Agents migration completed!")
