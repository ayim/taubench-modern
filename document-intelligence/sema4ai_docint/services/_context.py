from dataclasses import dataclass

from sema4ai.data import DataSource

from sema4ai_docint.agent_server_client.transport.base import TransportBase
from sema4ai_docint.agent_server_client.transport.http import HTTPTransport
from sema4ai_docint.extraction.reducto.async_ import AsyncExtractionClient
from sema4ai_docint.extraction.reducto.sync import SyncExtractionClient
from sema4ai_docint.models.initialize import initialize_database
from sema4ai_docint.services.persistence import (
    ParsedDocumentPersistence,
)

from ..agent_server_client import AgentServerClient


@dataclass
class _DIContext:
    """Shared context containing all external dependencies for document intelligence services.

    This context provides centralized access to database connections and external clients,
    avoiding complex dependency injection while maintaining type safety.
    """

    # Core database connection
    datasource: DataSource

    # Optional extraction clients
    extraction_service: SyncExtractionClient | None = None
    extraction_service_async: AsyncExtractionClient | None = None

    # Optional agent server transport
    agent_server_transport: TransportBase | None = None

    # Lazy-loaded agent client to avoid initialization requests
    _agent_client: AgentServerClient | None = None

    # PGVector datasource (required for the knowledge base service creation)
    pg_vector: DataSource | None = None

    # Optional persistence service for caching expensive extraction operations
    persistence_service: ParsedDocumentPersistence | None = None

    @property
    def agent_client(self) -> AgentServerClient:
        """Lazy-loaded agent client that initializes only when first accessed."""
        if self._agent_client is None:
            self._agent_client = AgentServerClient(transport=self.agent_server_transport)
        return self._agent_client

    @classmethod
    def create(
        cls,
        datasource: DataSource,
        sema4_api_key: str | None = None,
        disable_ssl_verification: bool = False,
        *,
        agent_server_transport: TransportBase | None = None,
        pg_vector: DataSource | None = None,
        sema4_backend_url: str | None = None,
        persistence_service: ParsedDocumentPersistence | None = None,
    ) -> "_DIContext":
        extraction_service = None
        extraction_service_async = None
        if sema4_api_key:
            extraction_service = SyncExtractionClient(
                api_key=sema4_api_key,
                disable_ssl_verification=disable_ssl_verification,
                base_url=sema4_backend_url,
            )
            extraction_service_async = AsyncExtractionClient(
                api_key=sema4_api_key,
                disable_ssl_verification=disable_ssl_verification,
                base_url=sema4_backend_url,
            )

        if agent_server_transport is None:
            agent_server_transport = HTTPTransport()

        # Make sure the database is initialized up front.
        if datasource is not None:
            initialize_database(engine="postgres", datasource=datasource)

        return cls(
            datasource=datasource,
            extraction_service=extraction_service,
            extraction_service_async=extraction_service_async,
            agent_server_transport=agent_server_transport,
            pg_vector=pg_vector,
            persistence_service=persistence_service,
        )
