import json
from urllib.parse import parse_qs, urlparse

from pydantic import BaseModel
from sema4ai.data import DataSource, get_connection

from sema4ai_docint.agent_server_client.client import AgentServerClient
from sema4ai_docint.logging import logger
from sema4ai_docint.models.constants import (
    EMBEDDING_TABLE_NAME,
    KNOWLEDGE_BASE_NAME,
    PARSED_DOCUMENTS_TABLE_NAME,
    PROJECT_NAME,
)
from sema4ai_docint.models.initialize import initialize_project

from .exceptions import KnowledgeBaseServiceError

# HTTP status codes
HTTP_OK = 200

DEFAULT_EMBEDDING_MODELS = {
    "openai": "text-embedding-3-large",
    "azure": "text-embedding-3-large",
    # "bedrock": "amazon.titan-embed-text-v1",
    # "snowflake": "snowflake-arctic-embed-l",
}

AGENT_TO_MINDSDB_MODEL_MAPPING = {
    "gpt-5-high": "gpt-5",
    "gpt-5-medium": "gpt-5",
    "gpt-5-low": "gpt-5",
    "gpt-5-minimal": "gpt-5-nano",
    "gpt-5-mini": "gpt-5-mini",
    "gpt-4-1": "gpt-4.1",
    "gpt-4-1-mini": "gpt-4.1-mini",
    "gpt-4-1-nano": "gpt-4.1-nano",
    "gpt-4o": "gpt-4o",
    "gpt-4o-chatgpt": "chatgpt-4o-latest",
    "o4-mini-high": "o4-mini",
    "o4-mini-low": "o4-mini",
    "o3-high": "o3",
    "o3-low": "o3",
}


def _map_agent_model_to_mindsdb(agent_model_name: str) -> str:
    if agent_model_name in AGENT_TO_MINDSDB_MODEL_MAPPING:
        return AGENT_TO_MINDSDB_MODEL_MAPPING[agent_model_name]

    supported_models = list(AGENT_TO_MINDSDB_MODEL_MAPPING.keys())
    raise ValueError(
        f"Unsupported model name: '{agent_model_name}'. "
        f"Supported agent models: {supported_models}. "
    )


class OpenAILLMConfig(BaseModel):
    """OpenAI LLM configuration model."""

    provider: str
    name: str
    openai_api_key: str

    @classmethod
    def from_agent_config(cls, agent_data: dict) -> "OpenAILLMConfig":
        config = agent_data.get("config", {})
        return cls(
            provider=agent_data.get("provider"),
            name=agent_data.get("name"),
            openai_api_key=config.get("openai_api_key"),
        )

    def to_mindsdb_embedding(self) -> dict:
        """Generate MindsDB embedding model configuration."""
        return {
            "provider": "openai",
            "model_name": DEFAULT_EMBEDDING_MODELS[self.provider.lower()],
            "api_key": self.openai_api_key,
        }

    def to_mindsdb_reranking(self) -> dict:
        """Generate MindsDB reranking model configuration."""
        return {
            "provider": "openai",
            "model_name": "gpt-4o",
            "api_key": self.openai_api_key,
        }


class AzureLLMConfig(BaseModel):
    """Azure OpenAI LLM configuration model."""

    provider: str
    name: str
    endpoint: str
    api_key: str

    @classmethod
    def from_agent_config(cls, agent_data: dict) -> "AzureLLMConfig":
        config = agent_data.get("config", {})
        return cls(
            provider=agent_data.get("provider"),
            name=agent_data.get("name"),
            endpoint=config.get("chat_url"),
            api_key=config.get("chat_openai_api_key"),
        )

    def _extract_azure_params(self) -> dict[str, str]:
        """Extract base_url and api_version from endpoint."""
        params = {}

        parsed = urlparse(self.endpoint)
        query_params = parse_qs(parsed.query)

        params["base_url"] = f"{parsed.scheme}://{parsed.netloc}"
        params["api_version"] = query_params.get("api-version")[0]

        return params

    def to_mindsdb_embedding(self) -> dict:
        """Generate MindsDB embedding model configuration."""
        base_config = {
            "provider": "openai_azure",
            "model_name": DEFAULT_EMBEDDING_MODELS[self.provider.lower()],
            "api_key": self.api_key,
        }

        base_config.update(self._extract_azure_params())
        return base_config

    def to_mindsdb_reranking(self) -> dict:
        """Generate MindsDB reranking model configuration."""
        base_config = {
            "provider": "openai_azure",
            "model_name": "gpt-4o",
            "api_key": self.api_key,
        }

        base_config.update(self._extract_azure_params())
        return base_config


LLMConfig = OpenAILLMConfig | AzureLLMConfig


def _setup_kb(datasource: DataSource, pg_vector: DataSource) -> str:
    """Set up a complete knowledge base with PGVector storage and MindsDB configuration.

    Args:
        datasource: The PostgreSQL datasource to use
        kb_source: PGVector datasource and optional kb_name to use

    Returns:
        Success message indicating the KB was set up successfully

    Raises:
        KnowledgeBaseServiceError: If any step of the setup fails or if datasource is not PostgreSQL
    """
    try:
        initialize_project(PROJECT_NAME)

        _create_parsed_documents_table(datasource)

        storage_reference = f"{pg_vector.datasource_name}.{EMBEDDING_TABLE_NAME}"
        _create_knowledge_base(kb_name=KNOWLEDGE_BASE_NAME, storage_reference=storage_reference)

        return (
            f"Successfully set up knowledge base '{KNOWLEDGE_BASE_NAME}' "
            f"in project '{PROJECT_NAME}'"
        )

    except Exception as e:
        if isinstance(e, KnowledgeBaseServiceError):
            raise
        raise KnowledgeBaseServiceError(
            f"Failed to set up knowledge base '{KNOWLEDGE_BASE_NAME}': {e!s}"
        ) from e


def _create_llm_config(agent_model_data: dict) -> LLMConfig:
    """Create appropriate LLM config model from agent data."""
    provider = agent_model_data.get("provider", "").lower()

    if provider == "openai":
        return OpenAILLMConfig.from_agent_config(agent_model_data)
    elif provider == "azure":
        return AzureLLMConfig.from_agent_config(agent_model_data)
    else:
        supported_providers = list(DEFAULT_EMBEDDING_MODELS.keys())
        raise ValueError(
            f"Unsupported provider for KB operations: {provider}. "
            f"Supported providers are: {supported_providers}"
        )


def _get_agent_config() -> dict:
    """Get agent configuration including LLM and platform configs from the agent server.

    Returns:
        Dictionary containing agent configuration with llm_config and platform_configs

    Raises:
        KnowledgeBaseServiceError: If unable to fetch agent configuration
    """
    try:
        client = AgentServerClient()
        response = client.transport.request("GET", f"agents/{client.transport.agent_id}/raw")

        if response.status_code != HTTP_OK:
            raise KnowledgeBaseServiceError(
                f"Failed to fetch agent config: HTTP {response.status_code}"
            )

        agent_data = response.json()
        return agent_data

    except Exception as e:
        raise KnowledgeBaseServiceError(f"Failed to get agent configuration: {e!s}") from e


def _get_model_configs_from_agent() -> tuple[dict, dict]:
    """Get embedding and reranking model configurations from agent settings.

    Returns:
        Tuple of (embedding_config, reranking_config)
    """
    agent_config = _get_agent_config()
    model_data = agent_config.get("model")

    llm_config = _create_llm_config(model_data)

    embedding_config = llm_config.to_mindsdb_embedding()
    reranking_config = llm_config.to_mindsdb_reranking()

    return embedding_config, reranking_config


def _create_parsed_documents_table(datasource: DataSource) -> None:
    table_sql = f"""
    CREATE TABLE IF NOT EXISTS {PARSED_DOCUMENTS_TABLE_NAME} (
        id TEXT PRIMARY KEY NOT NULL,
        document_name TEXT,
        extracted_chunks JSONB
    )
    """
    datasource.native_query(table_sql)


def _knowledge_base_exists(kb_name: str) -> bool:
    kb_list = get_connection().list_knowledge_bases()

    for kb in kb_list:
        if kb.name == kb_name and kb.project == PROJECT_NAME:
            return True

    return False


def _create_knowledge_base(kb_name: str, storage_reference: str) -> None:
    try:
        if _knowledge_base_exists(kb_name):
            logger.info(
                f"Knowledge base '{PROJECT_NAME}.{kb_name}' already exists, skipping creation"
            )
            return

        embedding_model_config, reranking_model_config = _get_model_configs_from_agent()
        embedding_config = json.dumps(embedding_model_config)
        reranking_config = json.dumps(reranking_model_config)

        sql = f"""
        CREATE KNOWLEDGE_BASE {PROJECT_NAME}.{kb_name}
        USING
            embedding_model = {embedding_config},
            reranking_model = {reranking_config},
            storage = {storage_reference},
            metadata_columns = ["document_name"],
            content_columns = ["chunk_content"],
            id_column = 'document_id';
        """

        get_connection().execute_sql(sql)

        logger.info(f"Successfully created knowledge base '{PROJECT_NAME}.{kb_name}'")

    except Exception as e:
        raise KnowledgeBaseServiceError(
            f"Failed to create knowledge base '{kb_name}': {e!s}"
        ) from e
