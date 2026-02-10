import os
from collections.abc import Callable, Generator
from pathlib import Path
from typing import Any

import pytest
from agent_platform.orchestrator.agent_server_client import ActionPackage, AgentServerClient

from agent_platform.core.payloads.document_intelligence_config import (
    DocumentIntelligenceConfigPayload,
    IntegrationInput,
)
from agent_platform.core.utils import SecretString
from agent_platform.server.secret_manager.base import BaseSecretManager
from agent_platform.server.secret_manager.option import SecretService

SPAR_RESOURCES_PATH = Path(__file__).parent / "resources"


# TODO: Should we warn/error harder?
@pytest.fixture(scope="session")
def openai_api_key() -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY is not set.")
    return api_key


@pytest.fixture(scope="session")
def reducto_api_key() -> str:
    api_key = os.getenv("REDUCTO_API_KEY")
    if not api_key:
        pytest.skip("REDUCTO_API_KEY is not set.")
    return api_key


@pytest.fixture(scope="session")
def reducto_endpoint() -> str:
    return os.getenv("REDUCTO_ENDPOINT", "https://backend.sema4.ai/reducto")


@pytest.fixture(scope="session")
def spar_agent_server_base_url() -> str:
    # TODO: Should this read the compose file and just get it from there just to be safe?
    return os.getenv("SEMA4AI_WORKROOM_AGENT_SERVER_URL", "http://localhost:8000/api/v2")


@pytest.fixture(scope="session")
def agent_server_client(
    spar_agent_server_base_url: str,
    reducto_api_key: str,
    reducto_endpoint: str,
) -> Generator[AgentServerClient, Any, Any]:
    with AgentServerClient(spar_agent_server_base_url) as client:
        # Configure Reducto integration so document intelligence is available for all tests
        doc_int_config = DocumentIntelligenceConfigPayload(
            integrations=[
                IntegrationInput(
                    type="reducto",
                    endpoint=reducto_endpoint,
                    api_key=SecretString(reducto_api_key),
                ),
            ],
        )
        client.configure_document_intelligence(doc_int_config)

        yield client


@pytest.fixture(scope="session")
def agent_factory(agent_server_client: AgentServerClient, openai_api_key: str) -> Callable[[], str]:
    agents = []

    def _create_agent(
        runbook: str = "You are a helpful assistant.",
        platform_configs: list[dict[str, Any]] | None = None,
        action_packages: list[ActionPackage] | None = None,
        description: str = "This is a test agent",
    ) -> str:
        if action_packages is None:
            action_packages = []
        if platform_configs is None:
            platform_configs = [{"kind": "openai", "openai_api_key": openai_api_key}]
        agent_id = agent_server_client.create_agent_and_return_agent_id(
            action_packages=action_packages,
            platform_configs=platform_configs,
            runbook=runbook,
            document_intelligence="v2",
            description=description,
        )
        agents.append((agent_server_client, agent_id))
        return agent_id

    return _create_agent


@pytest.fixture(scope="session")
def spar_resources_path() -> Path:
    return SPAR_RESOURCES_PATH


@pytest.fixture(scope="session")
def spar_postgres_url() -> str:
    return os.getenv("POSTGRES_URL", "postgresql://agents:agents@localhost:5432/agents")


@pytest.fixture(scope="session")
def secret_service() -> BaseSecretManager:
    return SecretService.get_instance()


@pytest.fixture
def data_model_cleanup(
    spar_agent_server_base_url: str,
) -> Generator[Callable[[str, str], None], Any, Any]:
    """
    Fixture that provides a cleanup function for data models and automatically
    cleans up any registered models when the test finishes.

    Usage in test:
        cleanup_func = data_model_cleanup
        # ... create your data model ...
        cleanup_func(model_name, agent_id)  # Register for cleanup
    """
    cleanup_list: list[tuple[str, str]] = []  # [(model_name, agent_id), ...]

    def register_for_cleanup(model_name: str, agent_id: str) -> None:
        """Register a data model for cleanup after the test."""
        cleanup_list.append((model_name, agent_id))

    yield register_for_cleanup

    # Cleanup all registered data models
    for model_name, agent_id in cleanup_list:
        try:
            import httpx

            delete_resp = httpx.delete(
                f"{spar_agent_server_base_url}/document-intelligence/data-models/{model_name}?agent_id={agent_id}",
                timeout=30,
            )
            if delete_resp.status_code not in (200, 404):
                print(f"Warning: Failed to delete data model {model_name}: {delete_resp.text}")
        except Exception as e:
            print(f"Warning: Exception during data model cleanup for {model_name}: {e}")


@pytest.fixture
def layout_cleanup(
    spar_agent_server_base_url: str,
) -> Generator[Callable[[str, str], None], Any, Any]:
    """
    Class-scoped fixture that provides a cleanup function for document layouts.
    All layouts registered during the test class will be cleaned up when the class finishes.

    Usage in test class:
        def test_something(self, layout_cleanup):
            # ... create your layout ...
            layout_cleanup(layout_name, data_model_name)  # Register for cleanup
    """
    cleanup_list: list[tuple[str, str]] = []  # [(layout_name, data_model_name), ...]

    def register_for_cleanup(layout_name: str, data_model_name: str) -> None:
        """Register a layout for cleanup after the test class."""
        cleanup_list.append((layout_name, data_model_name))

    yield register_for_cleanup

    # Cleanup all registered layouts
    for layout_name, data_model_name in cleanup_list:
        try:
            import requests

            delete_resp = requests.delete(
                f"{spar_agent_server_base_url}/document-intelligence/layouts/{layout_name}",
                params={"data_model_name": data_model_name},
                timeout=30,
            )
            if delete_resp.status_code not in (200, 404):
                print(f"Warning: Failed to delete layout {layout_name}: {delete_resp.text}")
        except Exception as e:
            print(f"Warning: Exception during layout cleanup for {layout_name}: {e}")
